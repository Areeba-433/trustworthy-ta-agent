# Figures in answers: proposal (Minahil, for the team)

## The problem

Our course books are full of figures: the OOP book has 154, and 106 of them are pictures whose labels are part of
the image. Without OCR (out of scope) their words cannot be searched, and OCR would not help much anyway: it reads
the labels ("class A, private, protected") but loses the arrows, and in a diagram the arrows are the meaning.

## Options we compared

| | OCR the pictures | A model describes each picture at ingestion | Show the picture to the LLM at answer time |
|---|---|---|---|
| What the TA gets | Label words, no arrows | A generated description | The diagram itself |
| Risk | Misread labels | Generated text stored as if the book said it | Little: nothing is invented at ingestion |
| Cost | Minutes per book | One model call per figure (about 106 per book) | Nothing at ingestion; an image in the prompt only when a figure is retrieved |

Decision proposed: **show the picture at answer time.**

## What is built (PDF track, no contract change)

- `mark_figures()` (`app/ingestion/pdf_figures.py`): the caption of every figure, and the words drawn inside it, get
  `extra["figure"] = {"page": 424, "box": [left, top, right, bottom]}`, the box as fractions of the visible page
  measured from its top-left corner.
- `render_figure(pdf_path, figure)` cuts that box out of the stored original PDF as a PNG: about 50 ms and 70 KB for
  Figure 9.7 at 150 dpi. No image is stored anywhere.

Retrieval finds a figure through its caption ("FIGURE 9.7 Public and private derivation") and the paragraph that
refers to it, which usually share a chunk. From the chunk, `block_seqs` lead to the blocks in `parsed.json`, and the
note on the caption block leads to the figure.

## Proposed contract change (needs all four to approve)

Today retrieval would have to read `parsed.json` and a PDF-track field in `Block.extra`, which the contract calls
track-private. Cleaner, as contract version 2.1:

```python
class FigureRef(_Strict):
    page: int = Field(ge=1)
    box: tuple[float, float, float, float]     # left, top, right, bottom: fractions of the visible page

class Chunk(_Strict):
    ...
    figures: list[FigureRef] = Field(default_factory=list)   # figures whose caption or inner words are in the chunk
```

The PDF chunker fills `figures`; every other format leaves it empty, so DOCX, PPTX, code, text and audio are
unchanged.

## At answer time (for whoever builds retrieval and the agent)

1. When a retrieved chunk has `figures` and the question is about what the figure shows, render at most one or two.
2. Give them to the LLM with the text, and show them to the student next to the answer as the source.
3. Cache each rendered figure (key: file hash + page + box); the same figure is asked about again and again.

This needs the original uploaded file to be kept by the storage layer.

## Questions for the team

1. Does the LLM we use accept images, and what does an image cost per answer in tokens and time?
2. How many images may one answer carry (proposal: at most 2)?
3. Measure before deciding: the same question with and without the picture, time to the first word of the answer.
   We already track response time and API calls.

## Known limits

- A figure with no caption and no words inside it has no block to carry its place, so it is not offered.
- A figure split over two pages is not placed.
- The boxes assume Docling measures on its visible page, which is true for its default PDF reader (docling-parse).
  If we switch readers (the crash investigation may), check this first.
