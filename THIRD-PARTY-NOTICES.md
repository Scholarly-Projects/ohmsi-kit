# Third-party notices

The ohmsi-kit code is licensed under the MIT License in [LICENSE](LICENSE). This repository also includes the material below, distributed under its own license or rights statement.

## Oral History as Data collections template

The transcript editing workspace in `_local-build/` is built from the [Oral History as Data collections template](https://github.com/uidaholib/oral-history-collections-template), which is based on [CollectionBuilder](https://collectionbuilder.github.io/). Files copied from the template, unchanged or adapted, include:

- `_local-build/_includes/head/` and `_local-build/_includes/foot.html`
- `_local-build/_includes/transcript/`
- `_local-build/_sass/`
- `_local-build/assets/css/cb.scss` and `_local-build/assets/lib/`
- `_local-build/_data/theme.yml`, `config-theme-colors.csv` and `filters.csv`
- `_local-build/_layouts/editor.html` and `editor-base.html`, adapted from the template's transcript and item page layouts

These files are used under the following license:

```
MIT License

Copyright (c) 2021 CollectionBuilder contributors, evanwill, dcnb, owikle, jylisadoney, University of Idaho Library Digital Initiatives, https://www.lib.uidaho.edu/digital/

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Example recording

`A/example_fisher_marie.mp3` is an excerpt (the first 15 minutes) of an interview from the Latah County Oral History Collection, included for instructional purposes. The example transcripts, `B/example_fisher_marie.csv` and `C/example_fisher_marie.csv`, cover the same excerpt.

> "Marie Leitch Fisher Interview #1, 10/29/1975", Latah County Oral History Collection, University of Idaho Library Digital Collections, https://www.lib.uidaho.edu/digital/lcoh/people/fisher_marie_1.html

**Rights:** In Copyright – Educational Use Permitted ([InC-EDU](http://rightsstatements.org/vocab/InC-EDU/1.0/)). This excerpt is not covered by the MIT License. For other uses, contact the University of Idaho Library Special Collections and Archives Department at libspec@uidaho.edu.

## Libraries installed separately

Whisper (MIT License), SpeechBrain (Apache License 2.0) and the other Python packages in `requirements.txt`, Jekyll and the Ruby gems in `Gemfile`, and Bootstrap (loaded from the web) are installed or loaded separately and are not included in this repository. Each is distributed under its own license.