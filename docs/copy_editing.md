# Copy Editing Workflow

This overview assumes you're keeping basic tracking notes (e.g. a `notes.md` file) and a shared reference list of proper nouns (e.g. a `semantic-list.md` file) alongside your transcripts. These are suggested conventions, not required infrastructure — adapt them to whatever tracking method works for your project.

- **First**, check whether there are major errors serious enough to warrant reprocessing the audio with a different script, rather than manually correcting the transcript.
    - Open the file locally and skip ahead roughly every 15 minutes to spot-check for major issues.
    - If you encounter major diarization problems — such as the transcript failing to flag distinct speakers in the middle of a dialogue exchange — reprocessing the audio may take less time than manually correcting it, so it's worth finding this out before investing more work.
    - If that's the case, log the filename of the affected transcript under a `reprocess with new script` heading in your tracking notes.
- **Second**, if the transcript looks workable, begin formatting it as needed using any of the processes detailed in the [Premiere Transcript Remediation Workflows](#premiere-transcript-remediation-workflows) section above:
    - [Remove millisecond from timestamps](#remove-millisecond-from-timestamps) (Premiere transcripts)
    - [Switch columns C and D](#switch-columns-c-and-d-for-copy-editing-dialogue) — retain, but don't prioritize, the End Time field if this is a Premiere transcript
    - [Remove empty line breaks from the CSV](#remove-empty-rows-between-dialogue-occasional-premiere-bug) (occasional Premiere bug)
    - [Capitalize the first letter in a new row of dialogue](#capitalize-first-letter-in-a-new-row-of-dialogue-occasional-premiere-and-whisper-bug) (occasional Premiere and Whisper bug)
    - [Change speaker names for specific sections](#change-speaker-names-for-specific-sections)
- **Third**, check the spelling in Visual Studio Code (or your editor of choice).
    - Look up flagged words.
    - Check your project's reference list (e.g. `semantic-list.md`) for people and place names that have already been documented.
    - If a proper name feels recurring, add it to the reference list, then right-click the word in your editor and select `Add to User Settings` to expand your personal dictionary.
    - If you're noticing a fair amount of mis-diarization caused by the interviewee posing rhetorical questions or recounting someone else's questions — such as "... and then she said, why did you do that?" — this is a good point in the workflow to run the **said.py** script on the file.
- **Fourth**, listen through the transcript by tabbing through the timestamp field while playing the corresponding audio locally.
    - This gives you a chance to correct diarization errors and refine spelling further.
    - **Note**: the goal is to reflect the audio, not correct it. Muffled recordings, mumbled words, and ambiguous proper names can be documented with an ellipsis or a best guess, as long as the guess is standardized across that transcript.
    - As you work through, note things like incorrect interviewer/interviewee metadata, sensitive material that should be flagged for researchers, and notes about the audio itself (looping, noise issues, etc.) in your tracking notes.
- **Fifth**, if the transcript is over-parsed, run **cluster.py** on the file, which will condense multiple rows of dialogue from the same speaker into clusters of up to four sentences.