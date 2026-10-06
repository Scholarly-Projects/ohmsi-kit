# frozen_string_literal: true

# Transcript editing workspace loader
#
# Folder layout (paths relative to the toolkit root, set under `editor:` in _config.yml):
#   A/             original recordings          C/            the ONE transcript being edited
#   B/             generated transcripts        _local-build/ everything Jekyll needs
#
# On every build (including each rebuild triggered by saving the CSV), this plugin:
#   1. finds the single transcript CSV in C/ and loads it into site.data.transcripts,
#      so the OHD transcript includes render it,
#   2. finds the recording with the same filename in A/, makes an MP3 playback copy
#      with ffmpeg when needed, and publishes only that file at /audio/,
#   3. checks the CSV for problems worth flagging while copy editing,
#   4. publishes _local-build/assets/ at /assets/ (CSS, icons, libraries),
#   5. generates the editing page at the site root (index.html, layout "editor").
# While `jekyll serve` runs, it also serves recordings in short, uncached pieces and
# prints the workspace address after each build.

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

  # recordings are published at /audio/<name>
  AUDIO_URL_DIR = 'audio'

  # largest piece of a recording sent in one response (see AudioRanges)
  AUDIO_CHUNK = 2 * 1024 * 1024

  def self.settings(config)
    editor = config['editor'] || {}
    {
      'transcript' => (editor['transcript_dir'] || 'C').to_s.chomp('/'),
      'audio' => (editor['audio_dir'] || 'A').to_s.chomp('/'),
      'build' => (editor['build_dir'] || '_local-build').to_s.chomp('/')
    }
  end

  # A file published at a fixed URL, wherever it is read from
  class MountedFile < Jekyll::StaticFile
    def initialize(site, source_dir, name, published_path)
      super(site, source_dir, '', name)
      @published_path = published_path
    end

    def destination(dest)
      File.join(dest, @published_path)
    end

    def url
      "/#{@published_path}"
    end
  end

  # Serves recordings under /audio/ in short, uncached pieces.
  # WEBrick (the server behind `jekyll serve`) answers an open-ended request such as
  # "bytes=1000000-" with the whole rest of the file and holds the connection open while
  # the browser reads it, and lets the browser cache and revalidate pieces of the file.
  # With long recordings that can leave a browser waiting on stale connections or cache
  # entries after a seek or a reload. Short pieces, Accept-Ranges and no-store avoid both.
  module AudioRanges
    def do_GET(req, res)
      path = @local_path.to_s
      ext = File.extname(path).delete('.').downcase
      return super unless AUDIO_TYPES.key?(ext) && path.include?("/#{AUDIO_URL_DIR}/")

      size = File.size(path)
      res['content-type'] = AUDIO_TYPES[ext]
      res['accept-ranges'] = 'bytes'
      res['cache-control'] = 'no-store'

      range = req['range'].to_s
      if (m = /\Abytes=(\d*)-(\d*)\z/.match(range.strip))
        if m[1].empty? # suffix range, e.g. bytes=-500
          first = [size - m[2].to_i, 0].max
          last = size - 1
        else
          first = m[1].to_i
          last = m[2].empty? ? size - 1 : [m[2].to_i, size - 1].min
        end
        raise WEBrick::HTTPStatus::RequestRangeNotSatisfiable if first >= size || last < first

        last = [last, first + AUDIO_CHUNK - 1].min
        res['content-range'] = "bytes #{first}-#{last}/#{size}"
        res['content-length'] = (last - first + 1).to_s
        res.body = File.open(path, 'rb')
        raise WEBrick::HTTPStatus::PartialContent
      end

      res['content-length'] = size.to_s
      res.body = File.open(path, 'rb')
    end
  end

  class Generator < Jekyll::Generator
    safe true
    priority :highest

    def generate(site)
      config = site.config['editor'] || {}
      dirs = EditorWorkspace.settings(site.config)
      preference = Array(config['audio_preference'] || AUDIO_TYPES.keys).map { |e| e.to_s.downcase }
      copy_mode = (config['playback_copy'] || 'auto').to_s.downcase

      @notices = []
      site.pages.reject! { |p| p.url == '/' }
      # C/ stays included so Jekyll watches it for saves, but nothing in it is published
      prefix = "#{dirs['transcript']}/"
      site.static_files.reject! { |f| f.relative_path.sub(%r{\A/}, '').start_with?(prefix) }

      mount_assets(site, dirs['build'])

      data = {
        'layout' => 'editor',
        'title' => 'Editing workspace',
        # same value an OHD metadata row gives a transcript item
        'display_template' => 'transcript'
      }

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

    # Publish everything in _local-build/assets/ at /assets/: files with front matter
    # (such as css/cb.scss) are rendered as pages, everything else is copied as-is.
    def mount_assets(site, build_dir)
      base = File.join(site.source, build_dir)
      root = File.join(base, 'assets')
      return unless Dir.exist?(root)

      Dir.glob('**/*', File::FNM_DOTMATCH, base: root).sort.each do |rel|
        full = File.join(root, rel)
        next if File.directory?(full) || File.basename(rel).start_with?('.')

        if Jekyll::Utils.has_yaml_header?(full)
          site.pages << Jekyll::Page.new(site, base, File.join('assets', File.dirname(rel)).chomp('/.'), File.basename(rel))
        else
          site.static_files << MountedFile.new(site, File.dirname(full), File.basename(rel), File.join('assets', rel))
        end
      end
    end

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
        published = "#{basename}.mp3"
        site.static_files << MountedFile.new(site, File.dirname(copy), File.basename(copy), "#{AUDIO_URL_DIR}/#{published}")
        type = AUDIO_TYPES['mp3']
      else
        published = chosen
        site.static_files << MountedFile.new(site, full, chosen, "#{AUDIO_URL_DIR}/#{published}")
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

    # Returns the path of a cached constant-bitrate MP3 copy of the recording,
    # or nil to play the original.
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
      out = File.join(cache_dir, "#{basename}-#{key}.mp3")
      return out if File.exist?(out)

      FileUtils.mkdir_p(cache_dir)
      Dir.glob(File.join(cache_dir, "#{basename}-*")).each { |old| File.delete(old) }
      Jekyll.logger.info 'Editor:', "Making a playback copy of #{File.basename(source)} (first time only)..."
      tmp = File.join(cache_dir, "#{basename}-#{key}.part.mp3")
      ok = system(ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                  '-i', source, '-vn', '-c:a', 'libmp3lame', '-b:a', '128k', tmp, err: File::NULL)
      if ok && File.size?(tmp)
        File.rename(tmp, out)
        return out
      end

      FileUtils.rm_f(tmp)
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

begin
  require 'webrick'
  WEBrick::HTTPServlet::DefaultFileHandler.prepend(EditorWorkspace::AudioRanges)
rescue LoadError
  # webrick is only needed for `jekyll serve`
end

# While `jekyll serve` runs, print the workspace address after each build so it can be
# copied (or Cmd/Ctrl+clicked in most terminals) without the browser opening by itself.
# 127.0.0.1 is the address Jekyll listens on; "localhost" can resolve elsewhere first.
Jekyll::Hooks.register :site, :post_write do |site|
  next unless site.config['serving']

  host = site.config['host'].to_s
  host = '127.0.0.1' if host.empty? || host == 'localhost'
  scheme = site.config['ssl_cert'] && site.config['ssl_key'] ? 'https' : 'http'
  Jekyll.logger.info 'Workspace:', "#{scheme}://#{host}:#{site.config['port']}#{site.config['baseurl']}/"
end