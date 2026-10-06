# frozen_string_literal: true

# Transcript editing workspace loader
#
# On every build (including each rebuild triggered by saving the CSV), this plugin:
#   1. finds the single transcript CSV in the transcript folder (C/ by default),
#   2. loads it into site.data.transcripts so the OHD transcript includes can render it,
#   3. finds the recording with the same filename in the audio folder (A/ by default)
#      and copies only that file into _site,
#   4. checks the CSV for problems worth flagging while copy editing,
#   5. generates the editing page at the site root (index.html, layout "editor").
#
# Settings live under `editor:` in _config.yml.

require 'csv'
require 'erb'

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

  class Generator < Jekyll::Generator
    safe true
    priority :highest

    def generate(site)
      config = site.config['editor'] || {}
      transcript_dir = (config['transcript_dir'] || 'C').to_s.chomp('/')
      audio_dir = (config['audio_dir'] || 'A').to_s.chomp('/')
      preference = Array(config['audio_preference'] || AUDIO_TYPES.keys).map { |e| e.to_s.downcase }

      @notices = []

      # The transcript folder must stay included so Jekyll watches it for saves,
      # but nothing in it needs to be copied to _site.
      prefix = "#{transcript_dir}/"
      site.static_files.reject! { |f| f.relative_path.sub(%r{\A/}, '').start_with?(prefix) }
      site.pages.reject! { |p| p.relative_path.sub(%r{\A/}, '').start_with?(prefix) || p.url == '/' }

      data = {
        'layout' => 'editor',
        'title' => 'Editing workspace',
        'built_at' => Time.now.strftime('%-I:%M:%S %p'),
        'transcript_dir' => transcript_dir,
        'audio_dir' => audio_dir
      }

      csv_path = pick_transcript(site, transcript_dir)
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
          'source_csv' => "#{transcript_dir}/#{filename}",
          'row_count' => (rows || []).size,
          'columns' => columns || [],
          'has_tags' => (columns || []).include?('tags'),
          'audio' => find_audio(site, audio_dir, basename, preference)
        )
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
        @notices << "There is no #{dir}/ folder. Create it and drop one transcript CSV from B/ into it."
        return nil
      end

      csvs = Dir.children(full)
                .reject { |f| f.start_with?('.', '~$') } # hidden and Excel lock files
                .select { |f| File.extname(f).casecmp?('.csv') }
                .map { |f| File.join(full, f) }

      case csvs.size
      when 0
        @notices << "#{dir}/ is empty. Copy one transcript CSV from B/ into #{dir}/ and save; the page reloads by itself."
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

    def find_audio(site, audio_dir, basename, preference)
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

      # A/ is excluded from the build; copy just this one recording into _site.
      site.static_files << Jekyll::StaticFile.new(site, site.source, audio_dir, chosen)
      ext = File.extname(chosen).delete('.').downcase
      {
        'name' => chosen,
        'url' => "/#{audio_dir}/#{ERB::Util.url_encode(chosen)}",
        'type' => AUDIO_TYPES[ext]
      }
    end
  end
end
