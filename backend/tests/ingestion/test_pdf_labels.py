"""theorem_labels() and drop_blank_page_notes(): headings that are only a theorem's label, and blank-page notes."""
from app.ingestion.contract import Block
from app.ingestion.pdf_labels import drop_blank_page_notes, is_label, theorem_labels

BOOK = "Data Structures"


def block(seq: int, kind: str, text: str, *path: str) -> Block:
    return Block(seq=seq, kind=kind, text=text, heading_path=[BOOK, *path], loc={"page": 343})


def test_a_label_alone_is_a_label_and_a_real_heading_is_not():
    assert all(is_label(t) for t in ["Proof", ". Proof", "Theorem 7.6", "Lemma 7.2.", "Example:", "Definition 3",
                                     "Theorem 7.8 (restated)", "Theorem 10.10 (Fermat's Lesser Theorem)",
                                     "Proof (By induction on the number of digits in n)"])
    assert not any(is_label(t) for t in ["7.8.1 Decision Trees", "Proof of Theorem 7.6", "Examples of Recursion",
                                         "Theorem Proving", "Proof by Induction", "Proof by Contradiction"])


def test_a_lemma_and_its_proof_stay_in_their_section():
    """DataStructures.pdf pages 343-344: "Lemma 7.2" and "Proof" were headings, so the lemma (20 tokens) and its
    proof ("Immediate from the preceding lemma.", 10 tokens) were two sections and two chunks."""
    section = "7.8.1 Decision Trees"
    blocks = [block(0, "heading", section, section),
              block(1, "paragraph", "A decision tree is an abstraction used to prove lower bounds.", section),
              block(2, "heading", "Lemma 7.2", section, "Lemma 7.2"),
              block(3, "paragraph", "A binary tree with L leaves must have depth at least log L.", section, "Lemma 7.2"),
              block(4, "heading", "Proof", section, "Proof"),
              block(5, "paragraph", "Immediate from the preceding lemma.", section, "Proof"),
              block(6, "heading", "7.9 Decision-Tree Lower Bounds", "7.9 Decision-Tree Lower Bounds"),
              block(7, "paragraph", "This section uses decision trees.", "7.9 Decision-Tree Lower Bounds")]
    out = theorem_labels(blocks)
    assert [(b.seq, b.kind, b.heading_path[1:]) for b in out] == [
        (0, "heading", [section]), (1, "paragraph", [section]), (2, "paragraph", [section]),
        (3, "paragraph", [section]), (4, "paragraph", [section]), (5, "paragraph", [section]),
        (6, "heading", ["7.9 Decision-Tree Lower Bounds"]), (7, "paragraph", ["7.9 Decision-Tree Lower Bounds"])]
    assert out[2].text == "Lemma 7.2" and out[2].extra["from_heading"] is True
    assert "from_heading" not in out[0].extra


def test_a_heading_under_a_label_moves_up_with_it():
    blocks = [block(0, "heading", "Example:", "Hashing", "Example:"),
              block(1, "heading", "Step 1", "Hashing", "Example:", "Step 1"),
              block(2, "paragraph", "Insert 89.", "Hashing", "Example:", "Step 1")]
    assert [(b.kind, b.heading_path[1:]) for b in theorem_labels(blocks)] == [
        ("paragraph", ["Hashing"]), ("heading", ["Hashing", "Step 1"]), ("paragraph", ["Hashing", "Step 1"])]


def test_the_same_label_twice_in_a_row_keeps_both_in_the_section():
    """DataStructures.pdf page 606: two "Example:" headings in 12.4.3; the second has the same heading path as the
    first, and its blocks must still go back to 12.4.3, not one level higher."""
    sec = ["12.4 Suffix Arrays", "12.4.3 Linear-Time Construction"]
    blocks = [block(0, "heading", "Example:", *sec, "Example:"),
              block(1, "paragraph", "In our example, the mapping is A = 1.", *sec, "Example:"),
              block(2, "heading", "Example:", *sec, "Example:"),
              block(3, "paragraph", "In our example, if we look at the character set.", *sec, "Example:"),
              block(4, "heading", "12.5 k-d Trees", "12.5 k-d Trees")]
    assert [(b.kind, b.heading_path[1:]) for b in theorem_labels(blocks)] == [
        ("paragraph", sec), ("paragraph", sec), ("paragraph", sec), ("paragraph", sec),
        ("heading", ["12.5 k-d Trees"])]


def test_blank_page_notes_go_and_what_shares_their_block_stays():
    """DataStructures.pdf: the note 5 times, once run together with the title page's "Fourth Edition"."""
    blocks = [block(0, "paragraph", "Fourth Edition"),
              block(1, "paragraph", "This page intentionally left blank Fourth Edition"),
              block(2, "paragraph", "This page intentionally left blank"),
              block(3, "paragraph", "To my kind, brilliant, and inspiring Sara.")]
    out = drop_blank_page_notes(blocks)
    assert [(b.seq, b.text) for b in out] == [
        (0, "Fourth Edition"), (1, "Fourth Edition"), (2, "To my kind, brilliant, and inspiring Sara.")]


def test_code_that_mentions_a_blank_page_is_left_alone():
    blocks = [block(0, "code", 'cout << "This page intentionally left blank";')]
    assert drop_blank_page_notes(blocks) == blocks
