# ohmsi-kit Workflow

* Before beginning processing, organize recordings by how many speakers are supposed to be involved in each interview. Unexpected speakers will be given the designation "Unknown Speaker" in CSV output, but designating a `NUM_SPEAKERS` in the user configuration section at the top of the script will help inform how much variance between speakers will be involved in the recording.
  * If speaker diarization is not a priority and/or you are dealing with a large volume of recordings, writing `None` after `NUM_SPEAKERS` will default determination of different speakers to the `distance_threshold`.
* Move these organized `mp3`, `wav`, `m4a` or `flac` files into the `A` folder of the repository.
* First, batch process with `script_a`. This is the most basic, accurate script which requires no customization beyond the speaker number designation.
* Reviewing the output of the processed audio files as CSVs in the B folder, it should be apparent if the recording was processed correctly. Large clusters of dialogue and/or transcripts gradually losing punctuation are indicators that those audio files need more advanced processing.
* `script_b` is identical to `a`, but utilizes the `medium.en` Whisper model and `script_c` uses `large_v2`. These may result in higher accuracy of word identification and speaker differentiation but they will take longer to process. Also, there is a vulnerability to hallucination in `large_v2` which you will need to look out for, but it is not nearly as pronounced as tests using `large-v3-turbo`, the most current Whisper model.
* _If these two scripts also yield unsuccessful transcriptions, the following models implement more manual approaches that may be helpful for unique recordings_.
* `script_d` contains an active `distance_threshold`, which is engaged even if there is a number provided in the `NUM_SPEAKERS`. If you are finding that speakers are incorrectly being merged, lower from the default `.65`. If the same speaker is being identified as multiple speakers, increase from `.65`.
  * `script_d` also contains an `INTERJECTION` filter that may be helpful with specific interview styles. Some interjections may incorrectly cluster at the end of the previous speaker's dialogue, such as:

| speaker | timestamp | words |
| :---- | ----- | :---- |
| Speaker 3 | 0:00:00 | If you didn't pay up, well, it would cut you off the line. So her father is a secretary there. He climbed the pole and cut her off and the old lady came out and put you down. |
| Speaker 2 | 0:00:12 | This was Mrs. McKean? <mark>Yeah.</mark> |
| Speaker 3 | 0:00:16 | She was a woman that enjoyed getting out of the scrap, you know, just like old Gabriel Anderson or my dad. |
| Speaker 1 | 0:00:23 | Well, she wouldn't pick anything, but she wouldn't pick anything either. |
| Speaker 3 | 0:00:27 | Well, Anna Marie writes this article about this to you. I'm a darn fool. Instead of putting her dad in that did do it, she says, Mr. Roan, my dad, he called her a man. |
| Speaker 1 | 0:00:43 | He and his dad were batching right across the road from him at that time. |
| Speaker 2 | 0:00:47 | Well, so, but what really happened was Gabriel Anderson went... Her mother is a man. What happened? He climbed up the pole to cut it off? <mark>Yeah.</mark> |

- _The `INTERJECTION` function in the configuration of `script_d` allows you to build a custom vocabulary based on these speaking styles, remove them from the ends of dialogue and attach them to the correct speaker, such as:_

| speaker | timestamp | words |
| :---- | ----- | :---- |
| Speaker 1 | 0:00:00 | If you didn't pay up, they'll cut you off the line. So her father is a second-year in there. He climbed the pole to cut her off, and the old lady came out of the butcher knife. |
| Speaker 3 | 0:00:13 | This was Mrs. McKean? |
| Speaker 1 | 0:00:14 | <mark>Yeah.</mark> She was a woman that enjoyed getting into the scrap, you know, just like old Gabriel Anderson or my dad. |
| Speaker 2 | 0:00:23 | Well, she wouldn't take anything, but she wouldn't take anything either. |
| Speaker 1 | 0:00:27 | Well, Anna Marie writes this article about this deal, and the darn fool, instead of putting her dad in that did do it, she says, Mr. Roan, my dad. |
| Speaker 2 | 0:00:40 | They laid right across the road. He and his dad were batching right across the road from him at that time. |
| Speaker 3 | 0:00:47 | Well, so, but what really happened was Gabriel Anderson went... |
| Speaker 1 | 0:00:51 | Her mother is a man. |
| Speaker 3 | 0:00:52 | What happened? He climbed up the pole to cut it off? |
| Speaker 1 | 0:00:54 | <mark>Yeah.</mark> And she came out with a butcher knife. |

* `script_e` adds another level of manual control. Whisper biometrics for identifying and labeling speakers is supplemented with heuristic rules for finding the interviewer by identifying questions being posed throughout the interview. Additionally, you can force breaks in dialogue manually by adjusting the `PAUSE_THRESHOLD` number in the configuration. This can be a helpful backup script in circumstances where interviewer and interviewee language is more formal.
    * That said, this interviewer designation is programmatic rather than relying on the nuance of the Whisper and SpeechBrain models and may result in needing to correct certain elements of the transcript in future copy editing processes.
* `script_f` is a last resort to salvage extremely compromised audio. Instead of attempting to identify and label speakers, the script separates clusters of speech by a `PAUSE_THRESHOLD` that can be adjusted in the configuration section of the script.
    * This CSV output is ideal if you simply need to have the most likely transcription of the audio with no speaker differentiation. For greater accuracy, run the audio through Adobe Premiere's transcription model, [using my workshop](https://aweymo-ui.github.io/premiere_transcripts/) for reference. The Premiere transcription will likely have improved diarization but inferior translation than this script. Using the Premiere transcript as a base, update with Whisper's more accurate translation to salvage and synthesize results.