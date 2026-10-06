# frozen_string_literal: true

# Transcript editing workspace loader
#
# On every build (including each rebuild triggered by saving the CSV), this plugin:
#   1. finds the single transcript CSV in the transcript folder (_data/C/ by default),
#   2. loads it into site.data.transcripts so the OHD transcript includes render it,
#   3. finds the recording with the same filename in the audio folder (_data/A/),
#      optionally makes a seek-friendly playback copy with ffmpeg, and publishes
#      only that one file at /audio/,
#   4. checks the CSV for problems worth flagging while copy editing,
#   5. generates the editing page at the site root (index.html, layout "editor"),
#   6. prints the workspace address in the terminal while `jekyll serve` runs.
#
# Settings live under `editor:` in _config.yml.

require 'csv'
require 'digest'
require 'erb'
require 'fileutils'

module EditorWorkspace
  AUDIO_TYPES = {
    'mp3' => 'audio/mpeg',
    'm4a' => 'audio/mp4',
    'wav' => 'audio/wav',
    'flac' => 'audio/flac'
  }.freeze

  REQUIRED_COLUMNS = %w[speaker timestamp words].freeze

  # H:MM:SS, HH:MM:SS or MM:SS, optionally with fractional seconds
  TIMESTAMP = /\A(?:(\d+):)?(\d{1,2}):(\d{2})(?:[.,]\d+)?\z/

  # recordings published at /audio/<name>
  AUDIO_URL_DIR = 'audio'

  def self.folders(config)
    editor = config['editor'] || {}
    {
      'transcript' => (editor['transcript_dir'] || '_data/C').to_s.chomp('/'),
      'audio' => (editor['audio_dir'] || '_data/A').to_s.chomp('/'),
      'generated' => (editor['generated_dir'] || '_data/B').to_s.chomp('/')
    }
  end

  # Jekyll parses every CSV under _data on every build, and its data reader
  # ignores `exclude`. Skip the toolkit folders: _data/B can hold hundreds of
  # transcripts, and _data/C is read by this plugin, which reports a broken CSV
  # on the page instead of stopping the build.
  module SkipToolkitData
    def read_data_to(dir, data)
      skip = EditorWorkspace.folders(site.config).values.map { |d| File.expand_path(d, site.source) }
      return if skip.include?(File.expand_path(dir))

      super
    end
  end

  # A recording published at /audio/<name>, whatever folder it is read from
  class AudioFile < Jekyll::StaticFile
    def initialize(site, base, dir, name, published_name)
      super(site, base, dir, name)
      @published_name = published_name
    end

    def destination(dest)
      File.join(dest, AUDIO_URL_DIR, @published_name)
    end

    def url
      "/#{AUDIO_URL_DIR}/#{@published_name}"
    end
  end

  class Generator < Jekyll::Generator
    safe true
    priority :highest

    def generate(site)
      config = site.config['editor'] || {}
      dirs = EditorWorkspace.folders(site.config)
      preference = Array(config['audio_preference'] || AUDIO_TYPES.keys).map { |e| e.to_s.downcase }
      copy_mode = (config['playback_copy'] || 'auto').to_s.downcase

      @notices = []
      site.pages.reject! { |p| p.url == '/' }

      data = {
        'layout' => 'editor',
        'title' => 'Editing workspace',
        # same value an OHD metadata row gives a transcript item
        'display_template' => 'transcript',
        'built_at' => Time.now.strftime('%-I:%M:%S %p'),
        'has_scroll_to_top' => File.exist?(File.join(site.source, site.config['includes_dir'] || '_includes', 'scroll-to-top.html'))
      }

      unless File.exist?(File.join(site.source, 'assets', 'lib', 'cb-icons.svg'))
        @notices << 'assets/lib/cb-icons.svg is missing, so the back-to-top button and other icons are blank. ' \
                    'Copy it from the OHD project.'
      end

      csv_path = pick_transcript(site, dirs['transcript'])
      if csv_path
        filename = File.basename(csv_path)
        basename = File.basename(csv_path, File.extname(csv_path))
        key = Jekyll::Utils.slugify(basename, mode: 'pretty')
        rows, columns = read_rows(csv_path)
        check_rows(rows, columns) if rows

        site.data['transcripts'] ||= {}
        site.data['transcripts'][key] = rows || []

        data.merge!(
          'title' => basename,
          'objectid' => key,
          'object-transcript' => key,
          'source_csv' => "#{dirs['transcript']}/#{filename}",
          'row_count' => (rows || []).size,
          'columns' => columns || [],
          'audio' => find_audio(site, dirs['audio'], basename, preference, copy_mode)
        )
        # the OHD player (transcript/player/mp3.html) reads the recording from object_location
        data['object_location'] = data['audio']['url'] if data['audio']
      end

      data['editor_notices'] = @notices
      @notices.each { |n| Jekyll.logger.warn 'Editor:', n }

      page = Jekyll::PageWithoutAFile.new(site, site.source, '', 'index.html')
      page.content = ''
      page.data.merge!(data)
      site.pages << page
    end

    private

    def pick_transcript(site, dir)
      full = File.join(site.source, dir)
      unless Dir.exist?(full)
        @notices << "There is no #{dir}/ folder. Create it and copy one transcript CSV into it."
        return nil
      end

      csvs = Dir.children(full)
                .reject { |f| f.start_with?('.', '~$') } # hidden and Excel lock files
                .select { |f| File.extname(f).casecmp?('.csv') }
                .map { |f| File.join(full, f) }

      case csvs.size
      when 0
        @notices << "#{dir}/ is empty. Copy one transcript CSV into #{dir}/; the page reloads by itself."
        nil
      when 1
        csvs.first
      else
        chosen = csvs.max_by { |f| File.mtime(f) }
        @notices << "#{dir}/ holds #{csvs.size} CSV files; showing the most recently saved " \
                    "(#{File.basename(chosen)}). Move the others out of #{dir}/ to clear this message."
        chosen
      end
    end

    def read_rows(path)
      text = File.binread(path).force_encoding('UTF-8')
      text = text.delete_prefix("﻿")
      unless text.valid_encoding?
        # Excel on Windows often saves CSVs as Windows-1252
        text = text.force_encoding('Windows-1252').encode('UTF-8', invalid: :replace, undef: :replace)
        @notices << "#{File.basename(path)} is not saved as UTF-8, so some characters may display wrong. " \
                    'In VS Code, use "Save with Encoding" > UTF-8.'
      end

      rows = []
      csv = CSV.new(text, headers: true, header_converters: ->(h) { h.to_s.strip.downcase })
      index = 0
      lines_read = 1 # the header row
      csv.each do |row|
        # line in the file where this row starts; a quoted cell can span several lines,
        # so count physical lines rather than using CSV#lineno (which counts records)
        start_line = lines_read + 1
        lines_read += [csv.line.to_s.count("\n"), 1].max
        hash = {}
        row.each do |k, v|
          next if k.nil? || k.empty?

          hash[k] = v.nil? ? nil : v.strip
        end
        next if hash.values.all? { |v| v.nil? || v.empty? }

        hash['csv_line'] = start_line
        hash['row_index'] = index
        index += 1
        rows << hash
      end
      [rows, csv.headers.is_a?(Array) ? csv.headers.compact : []]
    rescue CSV::MalformedCSVError => e
      @notices << "#{File.basename(path)} can't be read as a CSV: #{e.message.chomp('.')}. " \
                  'This usually means a missing or extra double quote; fix it and save.'
      [nil, nil]
    end

    def check_rows(rows, columns)
      missing = REQUIRED_COLUMNS - columns
      unless missing.empty?
        @notices << "Missing column(s): #{missing.join(', ')}. The header row should include " \
                    "#{REQUIRED_COLUMNS.join(', ')} (tags and terms are optional)."
      end

      previous = nil
      untimed = 0
      rows.each do |row|
        flags = []
        stamp = row['timestamp'].to_s
        if stamp.empty?
          untimed += 1
        elsif (m = TIMESTAMP.match(stamp))
          seconds = (m[1].to_i * 3600) + (m[2].to_i * 60) + m[3].to_i
          flags << "seconds over 59 in #{stamp}" if m[3].to_i > 59
          flags << 'timestamp is earlier than the line before' if previous && seconds < previous
          previous = seconds
        else
          flags << "timestamp \"#{stamp}\" is not H:MM:SS"
        end
        flags << 'no words' if row['words'].to_s.empty?
        row['editor_flags'] = flags.join('; ') unless flags.empty?
      end

      @notices << "#{untimed} line(s) have no timestamp, so they can't be jumped to." if untimed.positive?
    end

    def find_audio(site, audio_dir, basename, preference, copy_mode)
      full = File.join(site.source, audio_dir)
      candidates = if Dir.exist?(full)
                     Dir.children(full).select do |f|
                       ext = File.extname(f).delete('.').downcase
                       AUDIO_TYPES.key?(ext) && File.basename(f, File.extname(f)).casecmp?(basename)
                     end
                   else
                     []
                   end

      if candidates.empty?
        @notices << "No recording named #{basename}.mp3, .m4a, .wav or .flac in #{audio_dir}/. " \
                    'The transcript is shown without a player.'
        return nil
      end

      chosen = candidates.min_by { |f| preference.index(File.extname(f).delete('.').downcase) || 99 }
      if candidates.size > 1
        @notices << "#{audio_dir}/ has #{candidates.size} recordings named #{basename}; playing #{chosen}."
      end

      ext = File.extname(chosen).delete('.').downcase
      source = File.join(full, chosen)
      copy = playback_copy(site, source, basename, ext, copy_mode)

      if copy
        copy_ext = File.extname(copy).delete('.')
        published = "#{basename}.#{copy_ext}"
        site.static_files << AudioFile.new(site, File.dirname(copy), '', File.basename(copy), published)
        type = AUDIO_TYPES[copy_ext]
      else
        site.static_files << AudioFile.new(site, full, '', chosen, chosen)
        published = chosen
        type = AUDIO_TYPES[ext]
      end

      {
        'name' => chosen,
        'path' => "#{audio_dir}/#{chosen}",
        'url' => "/#{AUDIO_URL_DIR}/#{ERB::Util.url_encode(published)}",
        'type' => type,
        'playback_copy' => !copy.nil?
      }
    end

    # Playback copy: constant-bitrate MP3, which decodes in every browser and seeks accurately.
    ENCODINGS = [
      ['mp3', %w[-c:a libmp3lame -b:a 128k]]
    ].freeze

    # Returns the path of a cached playback copy of the recording, or nil to play the original.
    def playback_copy(site, source, basename, ext, mode)
      return nil if mode == 'never'
      # the OHD player is an MP3 player, so by default every other format gets an MP3 copy
      return nil if mode == 'auto' && ext == 'mp3'

      ffmpeg = which('ffmpeg')
      unless ffmpeg
        @notices << "ffmpeg was not found, so #{File.basename(source)} is played as-is. " \
                    'Install ffmpeg, or set editor: playback_copy: never in _config.yml to hide this message.'
        return nil
      end

      stat = File.stat(source)
      key = Digest::SHA1.hexdigest("#{source}|#{stat.size}|#{stat.mtime.to_i}")[0, 12]
      cache_dir = File.join(site.source, '.jekyll-cache', 'editor-audio')
      prefix = File.join(cache_dir, "#{basename}-#{key}")
      cached = ENCODINGS.map { |e, _| "#{prefix}.#{e}" }.find { |f| File.exist?(f) }
      return cached if cached

      FileUtils.mkdir_p(cache_dir)
      Dir.glob(File.join(cache_dir, "#{basename}-*")).each { |old| File.delete(old) }
      Jekyll.logger.info 'Editor:', "Making a playback copy of #{File.basename(source)} (first time only)..."
      ENCODINGS.each do |copy_ext, args|
        out = "#{prefix}.#{copy_ext}"
        tmp = "#{prefix}.part.#{copy_ext}"
        ok = system(ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                    '-i', source, '-vn', *args, tmp, err: File::NULL)
        if ok && File.size?(tmp)
          File.rename(tmp, out)
          return out
        end
        FileUtils.rm_f(tmp)
      end
      @notices << "ffmpeg couldn't make a playback copy of #{File.basename(source)}, so it is played as-is."
      nil
    end

    def which(cmd)
      exts = ENV['PATHEXT'] ? ENV['PATHEXT'].split(';') : ['']
      ENV['PATH'].to_s.split(File::PATH_SEPARATOR).each do |dir|
        exts.each do |ext|
          exe = File.join(dir, "#{cmd}#{ext}")
          return exe if File.executable?(exe) && !File.directory?(exe)
        end
      end
      nil
    end
  end
end

Jekyll::DataReader.prepend(EditorWorkspace::SkipToolkitData)

# While `jekyll serve` runs, print the workspace address after each build so it can be
# copied (or Cmd/Ctrl+clicked in most terminals) without the browser opening by itself.
Jekyll::Hooks.register :site, :post_write do |site|
  next unless site.config['serving']

  host = site.config['host'].to_s
  host = 'localhost' if host.empty? || host == '127.0.0.1'
  scheme = site.config['ssl_cert'] && site.config['ssl_key'] ? 'https' : 'http'
  Jekyll.logger.info 'Workspace:', "#{scheme}://#{host}:#{site.config['port']}#{site.config['baseurl']}/"
end