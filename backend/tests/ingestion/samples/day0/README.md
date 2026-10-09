# Day-0 smoke samples (owner: Minahil)

Tiny generated files, one per source type, so the contract test exercises every
loader from day 0. Real course files go in `samples/<track>/`.

| File | Tests |
|---|---|
| `digital_two_pages.pdf` | Digital PDF, numbered headings, a footer on each page → Track 1 |
| `digital_with_picture.pdf` | Digital PDF with a picture over 40% of the page → Track 1, `large_image_pages == [1]` |
| `scanned_page.pdf` | Page that is only a picture of text → Track 2 |
| `garbled_text_layer.pdf` | Text layer of nonsense Latin letters (the InPage Urdu case) → Track 2 |
| `password_protected.pdf` | Encrypted (password `secret`) → must fail politely |
| `lab_manual.docx` | Headings, a numbered list, a table |
| `stacks.pptx` | Two slides with titles |
| `photo_of_text.png` | Image of printed text → Track 2 |
| `clip.wav` | Half a second of silence → Track 3 |
| `stack.cpp`, `course_outline.md`, `reading_list.txt` | Track 4 |
