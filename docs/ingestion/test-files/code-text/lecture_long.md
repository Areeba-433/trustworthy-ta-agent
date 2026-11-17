# Long Lecture Notes: Retrieval Systems and Applied AI

> Synthetic test corpus for chunking, embedding, metadata extraction, and semantic retrieval.

## Document profile

- Document ID: LECTURE-AI-2026-001
- Prepared by: Dr. Mariam Siddiqui
- Organization: Centre for Applied Computing
- Primary location: Lahore, Pakistan
- Revision date: 8 November 2026
- Intended use: local development and evaluation only

## Contents

1. Retrieval-Augmented Generation
2. Text Chunking
3. Vector Embeddings
4. Metadata Filtering
5. Evaluation and Retrieval Quality
6. Document Parsing
7. Hybrid Search
8. Responsible AI

## Lecture chapters

### Chapter 1: Retrieval-Augmented Generation

**Instructor:** Dr. Mariam Siddiqui  
**Case contributor:** Amina Rahman  
**Organization:** Open Knowledge Lab  
**Location:** Lahore  

RAG combines retrieval with language generation. A retriever finds relevant passages, and a generator uses those passages to produce a grounded response.

In the Open Knowledge Lab case study, Amina Rahman tested FAISS with a small collection of technical documents. The team stored source identifiers in PostgreSQL and recorded the experiment location as Lahore. The objective was to make retrieval explainable: every returned passage should retain a stable link to its original document and section.

#### Key concepts

- **Purpose:** Understand how retrieval-augmented generation contributes to a reliable knowledge assistant.
- **Input:** Clean text, source metadata, and a clearly defined retrieval question.
- **Processing:** Normalize the content, preserve useful boundaries, and record transformation steps.
- **Output:** Searchable passages with identifiers, text, and traceable source information.
- **Risk:** Removing too much context can make a passage ambiguous; keeping too much can reduce retrieval precision.

#### Worked example

Suppose Amina Rahman asks: “Which component helps a user find information about retrieval-augmented generation?” A useful system should retrieve this chapter and explain the role of FAISS. It should not claim that PostgreSQL performs every step. Each component has a distinct responsibility.

#### Practical notes

1. Keep the chapter title with the passage when creating chunks for retrieval-augmented generation.
2. Store the document ID, chapter number, and source filename as metadata.
3. Avoid splitting a definition from the sentence that explains its purpose.
4. Test both exact-name questions and paraphrased questions.
5. Inspect retrieved text manually before changing model parameters.

#### Review questions

- How would you explain retrieval-augmented generation to a new developer?
- Which information about Amina Rahman and Open Knowledge Lab should be stored as metadata?
- What could go wrong if a chunk contains only the phrase “this component”?
- How can a retrieval result be traced back to its source?

---

### Chapter 2: Text Chunking

**Instructor:** Dr. Mariam Siddiqui  
**Case contributor:** Bilal Ahmed  
**Organization:** Data Systems Group  
**Location:** Islamabad  

Chunking divides long documents into smaller passages while preserving enough context for retrieval. Fixed-size, sentence-aware, and semantic strategies make different trade-offs.

In the Data Systems Group case study, Bilal Ahmed tested LangChain with a small collection of technical documents. The team stored source identifiers in Python and recorded the experiment location as Islamabad. The objective was to make retrieval explainable: every returned passage should retain a stable link to its original document and section.

#### Key concepts

- **Purpose:** Understand how text chunking contributes to a reliable knowledge assistant.
- **Input:** Clean text, source metadata, and a clearly defined retrieval question.
- **Processing:** Normalize the content, preserve useful boundaries, and record transformation steps.
- **Output:** Searchable passages with identifiers, text, and traceable source information.
- **Risk:** Removing too much context can make a passage ambiguous; keeping too much can reduce retrieval precision.

#### Worked example

Suppose Bilal Ahmed asks: “Which component helps a user find information about text chunking?” A useful system should retrieve this chapter and explain the role of LangChain. It should not claim that Python performs every step. Each component has a distinct responsibility.

#### Practical notes

1. Keep the chapter title with the passage when creating chunks for text chunking.
2. Store the document ID, chapter number, and source filename as metadata.
3. Avoid splitting a definition from the sentence that explains its purpose.
4. Test both exact-name questions and paraphrased questions.
5. Inspect retrieved text manually before changing model parameters.

#### Review questions

- How would you explain text chunking to a new developer?
- Which information about Bilal Ahmed and Data Systems Group should be stored as metadata?
- What could go wrong if a chunk contains only the phrase “this component”?
- How can a retrieval result be traced back to its source?

---

### Chapter 3: Vector Embeddings

**Instructor:** Dr. Mariam Siddiqui  
**Case contributor:** Sara Malik  
**Organization:** Applied AI Centre  
**Location:** Karachi  

An embedding model maps text into a numerical vector space. Similar meanings may occupy nearby regions, enabling semantic search beyond exact keyword matching.

In the Applied AI Centre case study, Sara Malik tested Sentence Transformers with a small collection of technical documents. The team stored source identifiers in PyTorch and recorded the experiment location as Karachi. The objective was to make retrieval explainable: every returned passage should retain a stable link to its original document and section.

#### Key concepts

- **Purpose:** Understand how vector embeddings contributes to a reliable knowledge assistant.
- **Input:** Clean text, source metadata, and a clearly defined retrieval question.
- **Processing:** Normalize the content, preserve useful boundaries, and record transformation steps.
- **Output:** Searchable passages with identifiers, text, and traceable source information.
- **Risk:** Removing too much context can make a passage ambiguous; keeping too much can reduce retrieval precision.

#### Worked example

Suppose Sara Malik asks: “Which component helps a user find information about vector embeddings?” A useful system should retrieve this chapter and explain the role of Sentence Transformers. It should not claim that PyTorch performs every step. Each component has a distinct responsibility.

#### Practical notes

1. Keep the chapter title with the passage when creating chunks for vector embeddings.
2. Store the document ID, chapter number, and source filename as metadata.
3. Avoid splitting a definition from the sentence that explains its purpose.
4. Test both exact-name questions and paraphrased questions.
5. Inspect retrieved text manually before changing model parameters.

#### Review questions

- How would you explain vector embeddings to a new developer?
- Which information about Sara Malik and Applied AI Centre should be stored as metadata?
- What could go wrong if a chunk contains only the phrase “this component”?
- How can a retrieval result be traced back to its source?

---

### Chapter 4: Metadata Filtering

**Instructor:** Dr. Mariam Siddiqui  
**Case contributor:** Hamza Qureshi  
**Organization:** Digital Library Unit  
**Location:** Peshawar  

Metadata adds structured context such as source, author, section, date, and access level. Filters can narrow retrieval before or after vector similarity search.

In the Digital Library Unit case study, Hamza Qureshi tested Qdrant with a small collection of technical documents. The team stored source identifiers in JSON and recorded the experiment location as Peshawar. The objective was to make retrieval explainable: every returned passage should retain a stable link to its original document and section.

#### Key concepts

- **Purpose:** Understand how metadata filtering contributes to a reliable knowledge assistant.
- **Input:** Clean text, source metadata, and a clearly defined retrieval question.
- **Processing:** Normalize the content, preserve useful boundaries, and record transformation steps.
- **Output:** Searchable passages with identifiers, text, and traceable source information.
- **Risk:** Removing too much context can make a passage ambiguous; keeping too much can reduce retrieval precision.

#### Worked example

Suppose Hamza Qureshi asks: “Which component helps a user find information about metadata filtering?” A useful system should retrieve this chapter and explain the role of Qdrant. It should not claim that JSON performs every step. Each component has a distinct responsibility.

#### Practical notes

1. Keep the chapter title with the passage when creating chunks for metadata filtering.
2. Store the document ID, chapter number, and source filename as metadata.
3. Avoid splitting a definition from the sentence that explains its purpose.
4. Test both exact-name questions and paraphrased questions.
5. Inspect retrieved text manually before changing model parameters.

#### Review questions

- How would you explain metadata filtering to a new developer?
- Which information about Hamza Qureshi and Digital Library Unit should be stored as metadata?
- What could go wrong if a chunk contains only the phrase “this component”?
- How can a retrieval result be traced back to its source?

---

### Chapter 5: Evaluation and Retrieval Quality

**Instructor:** Dr. Mariam Siddiqui  
**Case contributor:** Noor Fatima  
**Organization:** Research Quality Office  
**Location:** Multan  

A retrieval system should be evaluated with representative questions, expected source passages, relevance judgments, and measures such as recall at k and mean reciprocal rank.

In the Research Quality Office case study, Noor Fatima tested Ragas with a small collection of technical documents. The team stored source identifiers in Pandas and recorded the experiment location as Multan. The objective was to make retrieval explainable: every returned passage should retain a stable link to its original document and section.

#### Key concepts

- **Purpose:** Understand how evaluation and retrieval quality contributes to a reliable knowledge assistant.
- **Input:** Clean text, source metadata, and a clearly defined retrieval question.
- **Processing:** Normalize the content, preserve useful boundaries, and record transformation steps.
- **Output:** Searchable passages with identifiers, text, and traceable source information.
- **Risk:** Removing too much context can make a passage ambiguous; keeping too much can reduce retrieval precision.

#### Worked example

Suppose Noor Fatima asks: “Which component helps a user find information about evaluation and retrieval quality?” A useful system should retrieve this chapter and explain the role of Ragas. It should not claim that Pandas performs every step. Each component has a distinct responsibility.

#### Practical notes

1. Keep the chapter title with the passage when creating chunks for evaluation and retrieval quality.
2. Store the document ID, chapter number, and source filename as metadata.
3. Avoid splitting a definition from the sentence that explains its purpose.
4. Test both exact-name questions and paraphrased questions.
5. Inspect retrieved text manually before changing model parameters.

#### Review questions

- How would you explain evaluation and retrieval quality to a new developer?
- Which information about Noor Fatima and Research Quality Office should be stored as metadata?
- What could go wrong if a chunk contains only the phrase “this component”?
- How can a retrieval result be traced back to its source?

---

### Chapter 6: Document Parsing

**Instructor:** Dr. Mariam Siddiqui  
**Case contributor:** Usman Tariq  
**Organization:** Document Intelligence Team  
**Location:** Faisalabad  

Document parsing extracts text and structure from files. Headings, tables, lists, code blocks, and page boundaries can carry meaning that plain text extraction may lose.

In the Document Intelligence Team case study, Usman Tariq tested Docling with a small collection of technical documents. The team stored source identifiers in Apache Tika and recorded the experiment location as Faisalabad. The objective was to make retrieval explainable: every returned passage should retain a stable link to its original document and section.

#### Key concepts

- **Purpose:** Understand how document parsing contributes to a reliable knowledge assistant.
- **Input:** Clean text, source metadata, and a clearly defined retrieval question.
- **Processing:** Normalize the content, preserve useful boundaries, and record transformation steps.
- **Output:** Searchable passages with identifiers, text, and traceable source information.
- **Risk:** Removing too much context can make a passage ambiguous; keeping too much can reduce retrieval precision.

#### Worked example

Suppose Usman Tariq asks: “Which component helps a user find information about document parsing?” A useful system should retrieve this chapter and explain the role of Docling. It should not claim that Apache Tika performs every step. Each component has a distinct responsibility.

#### Practical notes

1. Keep the chapter title with the passage when creating chunks for document parsing.
2. Store the document ID, chapter number, and source filename as metadata.
3. Avoid splitting a definition from the sentence that explains its purpose.
4. Test both exact-name questions and paraphrased questions.
5. Inspect retrieved text manually before changing model parameters.

#### Review questions

- How would you explain document parsing to a new developer?
- Which information about Usman Tariq and Document Intelligence Team should be stored as metadata?
- What could go wrong if a chunk contains only the phrase “this component”?
- How can a retrieval result be traced back to its source?

---

### Chapter 7: Hybrid Search

**Instructor:** Dr. Mariam Siddiqui  
**Case contributor:** Hira Shah  
**Organization:** Search Engineering Team  
**Location:** Rawalpindi  

Hybrid search combines lexical matching with vector similarity. Keyword search can preserve exact identifiers, while dense retrieval can find paraphrases and related concepts.

In the Search Engineering Team case study, Hira Shah tested Elasticsearch with a small collection of technical documents. The team stored source identifiers in BM25 and recorded the experiment location as Rawalpindi. The objective was to make retrieval explainable: every returned passage should retain a stable link to its original document and section.

#### Key concepts

- **Purpose:** Understand how hybrid search contributes to a reliable knowledge assistant.
- **Input:** Clean text, source metadata, and a clearly defined retrieval question.
- **Processing:** Normalize the content, preserve useful boundaries, and record transformation steps.
- **Output:** Searchable passages with identifiers, text, and traceable source information.
- **Risk:** Removing too much context can make a passage ambiguous; keeping too much can reduce retrieval precision.

#### Worked example

Suppose Hira Shah asks: “Which component helps a user find information about hybrid search?” A useful system should retrieve this chapter and explain the role of Elasticsearch. It should not claim that BM25 performs every step. Each component has a distinct responsibility.

#### Practical notes

1. Keep the chapter title with the passage when creating chunks for hybrid search.
2. Store the document ID, chapter number, and source filename as metadata.
3. Avoid splitting a definition from the sentence that explains its purpose.
4. Test both exact-name questions and paraphrased questions.
5. Inspect retrieved text manually before changing model parameters.

#### Review questions

- How would you explain hybrid search to a new developer?
- Which information about Hira Shah and Search Engineering Team should be stored as metadata?
- What could go wrong if a chunk contains only the phrase “this component”?
- How can a retrieval result be traced back to its source?

---

### Chapter 8: Responsible AI

**Instructor:** Dr. Mariam Siddiqui  
**Case contributor:** Zain Ali  
**Organization:** Trustworthy Computing Forum  
**Location:** Quetta  

Responsible AI practice includes privacy, security, transparency, fairness, and human oversight. Teams should document limitations and test systems for unsafe or unsupported outputs.

In the Trustworthy Computing Forum case study, Zain Ali tested NIST AI RMF with a small collection of technical documents. The team stored source identifiers in Audit Logs and recorded the experiment location as Quetta. The objective was to make retrieval explainable: every returned passage should retain a stable link to its original document and section.

#### Key concepts

- **Purpose:** Understand how responsible ai contributes to a reliable knowledge assistant.
- **Input:** Clean text, source metadata, and a clearly defined retrieval question.
- **Processing:** Normalize the content, preserve useful boundaries, and record transformation steps.
- **Output:** Searchable passages with identifiers, text, and traceable source information.
- **Risk:** Removing too much context can make a passage ambiguous; keeping too much can reduce retrieval precision.

#### Worked example

Suppose Zain Ali asks: “Which component helps a user find information about responsible ai?” A useful system should retrieve this chapter and explain the role of NIST AI RMF. It should not claim that Audit Logs performs every step. Each component has a distinct responsibility.

#### Practical notes

1. Keep the chapter title with the passage when creating chunks for responsible ai.
2. Store the document ID, chapter number, and source filename as metadata.
3. Avoid splitting a definition from the sentence that explains its purpose.
4. Test both exact-name questions and paraphrased questions.
5. Inspect retrieved text manually before changing model parameters.

#### Review questions

- How would you explain responsible ai to a new developer?
- Which information about Zain Ali and Trustworthy Computing Forum should be stored as metadata?
- What could go wrong if a chunk contains only the phrase “this component”?
- How can a retrieval result be traced back to its source?

---

### Supplementary Note 001: Retrieval-Augmented Generation

**Record ID:** NOTE-001  
**Reviewer:** Amina Rahman  
**Team:** Open Knowledge Lab  
**System:** FAISS  

This supplementary note revisits retrieval-augmented generation from the perspective of implementation and testing. RAG combines retrieval with language generation. A retriever finds relevant passages, and a generator uses those passages to produce a grounded response. The example is associated with Lahore, and the prototype records configuration details using PostgreSQL. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 001, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 002: Text Chunking

**Record ID:** NOTE-002  
**Reviewer:** Bilal Ahmed  
**Team:** Data Systems Group  
**System:** LangChain  

This supplementary note revisits text chunking from the perspective of implementation and testing. Chunking divides long documents into smaller passages while preserving enough context for retrieval. Fixed-size, sentence-aware, and semantic strategies make different trade-offs. The example is associated with Islamabad, and the prototype records configuration details using Python. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 002, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 003: Vector Embeddings

**Record ID:** NOTE-003  
**Reviewer:** Sara Malik  
**Team:** Applied AI Centre  
**System:** Sentence Transformers  

This supplementary note revisits vector embeddings from the perspective of implementation and testing. An embedding model maps text into a numerical vector space. Similar meanings may occupy nearby regions, enabling semantic search beyond exact keyword matching. The example is associated with Karachi, and the prototype records configuration details using PyTorch. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 003, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 004: Metadata Filtering

**Record ID:** NOTE-004  
**Reviewer:** Hamza Qureshi  
**Team:** Digital Library Unit  
**System:** Qdrant  

This supplementary note revisits metadata filtering from the perspective of implementation and testing. Metadata adds structured context such as source, author, section, date, and access level. Filters can narrow retrieval before or after vector similarity search. The example is associated with Peshawar, and the prototype records configuration details using JSON. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 004, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 005: Evaluation and Retrieval Quality

**Record ID:** NOTE-005  
**Reviewer:** Noor Fatima  
**Team:** Research Quality Office  
**System:** Ragas  

This supplementary note revisits evaluation and retrieval quality from the perspective of implementation and testing. A retrieval system should be evaluated with representative questions, expected source passages, relevance judgments, and measures such as recall at k and mean reciprocal rank. The example is associated with Multan, and the prototype records configuration details using Pandas. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 005, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 006: Document Parsing

**Record ID:** NOTE-006  
**Reviewer:** Usman Tariq  
**Team:** Document Intelligence Team  
**System:** Docling  

This supplementary note revisits document parsing from the perspective of implementation and testing. Document parsing extracts text and structure from files. Headings, tables, lists, code blocks, and page boundaries can carry meaning that plain text extraction may lose. The example is associated with Faisalabad, and the prototype records configuration details using Apache Tika. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 006, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 007: Hybrid Search

**Record ID:** NOTE-007  
**Reviewer:** Hira Shah  
**Team:** Search Engineering Team  
**System:** Elasticsearch  

This supplementary note revisits hybrid search from the perspective of implementation and testing. Hybrid search combines lexical matching with vector similarity. Keyword search can preserve exact identifiers, while dense retrieval can find paraphrases and related concepts. The example is associated with Rawalpindi, and the prototype records configuration details using BM25. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 007, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 008: Responsible AI

**Record ID:** NOTE-008  
**Reviewer:** Zain Ali  
**Team:** Trustworthy Computing Forum  
**System:** NIST AI RMF  

This supplementary note revisits responsible ai from the perspective of implementation and testing. Responsible AI practice includes privacy, security, transparency, fairness, and human oversight. Teams should document limitations and test systems for unsafe or unsupported outputs. The example is associated with Quetta, and the prototype records configuration details using Audit Logs. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 008, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 009: Retrieval-Augmented Generation

**Record ID:** NOTE-009  
**Reviewer:** Amina Rahman  
**Team:** Open Knowledge Lab  
**System:** FAISS  

This supplementary note revisits retrieval-augmented generation from the perspective of implementation and testing. RAG combines retrieval with language generation. A retriever finds relevant passages, and a generator uses those passages to produce a grounded response. The example is associated with Lahore, and the prototype records configuration details using PostgreSQL. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 009, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 010: Text Chunking

**Record ID:** NOTE-010  
**Reviewer:** Bilal Ahmed  
**Team:** Data Systems Group  
**System:** LangChain  

This supplementary note revisits text chunking from the perspective of implementation and testing. Chunking divides long documents into smaller passages while preserving enough context for retrieval. Fixed-size, sentence-aware, and semantic strategies make different trade-offs. The example is associated with Islamabad, and the prototype records configuration details using Python. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 010, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 011: Vector Embeddings

**Record ID:** NOTE-011  
**Reviewer:** Sara Malik  
**Team:** Applied AI Centre  
**System:** Sentence Transformers  

This supplementary note revisits vector embeddings from the perspective of implementation and testing. An embedding model maps text into a numerical vector space. Similar meanings may occupy nearby regions, enabling semantic search beyond exact keyword matching. The example is associated with Karachi, and the prototype records configuration details using PyTorch. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 011, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 012: Metadata Filtering

**Record ID:** NOTE-012  
**Reviewer:** Hamza Qureshi  
**Team:** Digital Library Unit  
**System:** Qdrant  

This supplementary note revisits metadata filtering from the perspective of implementation and testing. Metadata adds structured context such as source, author, section, date, and access level. Filters can narrow retrieval before or after vector similarity search. The example is associated with Peshawar, and the prototype records configuration details using JSON. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 012, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 013: Evaluation and Retrieval Quality

**Record ID:** NOTE-013  
**Reviewer:** Noor Fatima  
**Team:** Research Quality Office  
**System:** Ragas  

This supplementary note revisits evaluation and retrieval quality from the perspective of implementation and testing. A retrieval system should be evaluated with representative questions, expected source passages, relevance judgments, and measures such as recall at k and mean reciprocal rank. The example is associated with Multan, and the prototype records configuration details using Pandas. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 013, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 014: Document Parsing

**Record ID:** NOTE-014  
**Reviewer:** Usman Tariq  
**Team:** Document Intelligence Team  
**System:** Docling  

This supplementary note revisits document parsing from the perspective of implementation and testing. Document parsing extracts text and structure from files. Headings, tables, lists, code blocks, and page boundaries can carry meaning that plain text extraction may lose. The example is associated with Faisalabad, and the prototype records configuration details using Apache Tika. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 014, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 015: Hybrid Search

**Record ID:** NOTE-015  
**Reviewer:** Hira Shah  
**Team:** Search Engineering Team  
**System:** Elasticsearch  

This supplementary note revisits hybrid search from the perspective of implementation and testing. Hybrid search combines lexical matching with vector similarity. Keyword search can preserve exact identifiers, while dense retrieval can find paraphrases and related concepts. The example is associated with Rawalpindi, and the prototype records configuration details using BM25. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 015, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 016: Responsible AI

**Record ID:** NOTE-016  
**Reviewer:** Zain Ali  
**Team:** Trustworthy Computing Forum  
**System:** NIST AI RMF  

This supplementary note revisits responsible ai from the perspective of implementation and testing. Responsible AI practice includes privacy, security, transparency, fairness, and human oversight. Teams should document limitations and test systems for unsafe or unsupported outputs. The example is associated with Quetta, and the prototype records configuration details using Audit Logs. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 016, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 017: Retrieval-Augmented Generation

**Record ID:** NOTE-017  
**Reviewer:** Amina Rahman  
**Team:** Open Knowledge Lab  
**System:** FAISS  

This supplementary note revisits retrieval-augmented generation from the perspective of implementation and testing. RAG combines retrieval with language generation. A retriever finds relevant passages, and a generator uses those passages to produce a grounded response. The example is associated with Lahore, and the prototype records configuration details using PostgreSQL. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 017, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 018: Text Chunking

**Record ID:** NOTE-018  
**Reviewer:** Bilal Ahmed  
**Team:** Data Systems Group  
**System:** LangChain  

This supplementary note revisits text chunking from the perspective of implementation and testing. Chunking divides long documents into smaller passages while preserving enough context for retrieval. Fixed-size, sentence-aware, and semantic strategies make different trade-offs. The example is associated with Islamabad, and the prototype records configuration details using Python. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 018, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 019: Vector Embeddings

**Record ID:** NOTE-019  
**Reviewer:** Sara Malik  
**Team:** Applied AI Centre  
**System:** Sentence Transformers  

This supplementary note revisits vector embeddings from the perspective of implementation and testing. An embedding model maps text into a numerical vector space. Similar meanings may occupy nearby regions, enabling semantic search beyond exact keyword matching. The example is associated with Karachi, and the prototype records configuration details using PyTorch. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 019, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 020: Metadata Filtering

**Record ID:** NOTE-020  
**Reviewer:** Hamza Qureshi  
**Team:** Digital Library Unit  
**System:** Qdrant  

This supplementary note revisits metadata filtering from the perspective of implementation and testing. Metadata adds structured context such as source, author, section, date, and access level. Filters can narrow retrieval before or after vector similarity search. The example is associated with Peshawar, and the prototype records configuration details using JSON. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 020, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 021: Evaluation and Retrieval Quality

**Record ID:** NOTE-021  
**Reviewer:** Noor Fatima  
**Team:** Research Quality Office  
**System:** Ragas  

This supplementary note revisits evaluation and retrieval quality from the perspective of implementation and testing. A retrieval system should be evaluated with representative questions, expected source passages, relevance judgments, and measures such as recall at k and mean reciprocal rank. The example is associated with Multan, and the prototype records configuration details using Pandas. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 021, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 022: Document Parsing

**Record ID:** NOTE-022  
**Reviewer:** Usman Tariq  
**Team:** Document Intelligence Team  
**System:** Docling  

This supplementary note revisits document parsing from the perspective of implementation and testing. Document parsing extracts text and structure from files. Headings, tables, lists, code blocks, and page boundaries can carry meaning that plain text extraction may lose. The example is associated with Faisalabad, and the prototype records configuration details using Apache Tika. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 022, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 023: Hybrid Search

**Record ID:** NOTE-023  
**Reviewer:** Hira Shah  
**Team:** Search Engineering Team  
**System:** Elasticsearch  

This supplementary note revisits hybrid search from the perspective of implementation and testing. Hybrid search combines lexical matching with vector similarity. Keyword search can preserve exact identifiers, while dense retrieval can find paraphrases and related concepts. The example is associated with Rawalpindi, and the prototype records configuration details using BM25. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 023, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 024: Responsible AI

**Record ID:** NOTE-024  
**Reviewer:** Zain Ali  
**Team:** Trustworthy Computing Forum  
**System:** NIST AI RMF  

This supplementary note revisits responsible ai from the perspective of implementation and testing. Responsible AI practice includes privacy, security, transparency, fairness, and human oversight. Teams should document limitations and test systems for unsafe or unsupported outputs. The example is associated with Quetta, and the prototype records configuration details using Audit Logs. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 024, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 025: Retrieval-Augmented Generation

**Record ID:** NOTE-025  
**Reviewer:** Amina Rahman  
**Team:** Open Knowledge Lab  
**System:** FAISS  

This supplementary note revisits retrieval-augmented generation from the perspective of implementation and testing. RAG combines retrieval with language generation. A retriever finds relevant passages, and a generator uses those passages to produce a grounded response. The example is associated with Lahore, and the prototype records configuration details using PostgreSQL. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 025, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 026: Text Chunking

**Record ID:** NOTE-026  
**Reviewer:** Bilal Ahmed  
**Team:** Data Systems Group  
**System:** LangChain  

This supplementary note revisits text chunking from the perspective of implementation and testing. Chunking divides long documents into smaller passages while preserving enough context for retrieval. Fixed-size, sentence-aware, and semantic strategies make different trade-offs. The example is associated with Islamabad, and the prototype records configuration details using Python. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 026, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 027: Vector Embeddings

**Record ID:** NOTE-027  
**Reviewer:** Sara Malik  
**Team:** Applied AI Centre  
**System:** Sentence Transformers  

This supplementary note revisits vector embeddings from the perspective of implementation and testing. An embedding model maps text into a numerical vector space. Similar meanings may occupy nearby regions, enabling semantic search beyond exact keyword matching. The example is associated with Karachi, and the prototype records configuration details using PyTorch. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 027, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 028: Metadata Filtering

**Record ID:** NOTE-028  
**Reviewer:** Hamza Qureshi  
**Team:** Digital Library Unit  
**System:** Qdrant  

This supplementary note revisits metadata filtering from the perspective of implementation and testing. Metadata adds structured context such as source, author, section, date, and access level. Filters can narrow retrieval before or after vector similarity search. The example is associated with Peshawar, and the prototype records configuration details using JSON. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 028, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 029: Evaluation and Retrieval Quality

**Record ID:** NOTE-029  
**Reviewer:** Noor Fatima  
**Team:** Research Quality Office  
**System:** Ragas  

This supplementary note revisits evaluation and retrieval quality from the perspective of implementation and testing. A retrieval system should be evaluated with representative questions, expected source passages, relevance judgments, and measures such as recall at k and mean reciprocal rank. The example is associated with Multan, and the prototype records configuration details using Pandas. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 029, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 030: Document Parsing

**Record ID:** NOTE-030  
**Reviewer:** Usman Tariq  
**Team:** Document Intelligence Team  
**System:** Docling  

This supplementary note revisits document parsing from the perspective of implementation and testing. Document parsing extracts text and structure from files. Headings, tables, lists, code blocks, and page boundaries can carry meaning that plain text extraction may lose. The example is associated with Faisalabad, and the prototype records configuration details using Apache Tika. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 030, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 031: Hybrid Search

**Record ID:** NOTE-031  
**Reviewer:** Hira Shah  
**Team:** Search Engineering Team  
**System:** Elasticsearch  

This supplementary note revisits hybrid search from the perspective of implementation and testing. Hybrid search combines lexical matching with vector similarity. Keyword search can preserve exact identifiers, while dense retrieval can find paraphrases and related concepts. The example is associated with Rawalpindi, and the prototype records configuration details using BM25. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 031, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 032: Responsible AI

**Record ID:** NOTE-032  
**Reviewer:** Zain Ali  
**Team:** Trustworthy Computing Forum  
**System:** NIST AI RMF  

This supplementary note revisits responsible ai from the perspective of implementation and testing. Responsible AI practice includes privacy, security, transparency, fairness, and human oversight. Teams should document limitations and test systems for unsafe or unsupported outputs. The example is associated with Quetta, and the prototype records configuration details using Audit Logs. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 032, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 033: Retrieval-Augmented Generation

**Record ID:** NOTE-033  
**Reviewer:** Amina Rahman  
**Team:** Open Knowledge Lab  
**System:** FAISS  

This supplementary note revisits retrieval-augmented generation from the perspective of implementation and testing. RAG combines retrieval with language generation. A retriever finds relevant passages, and a generator uses those passages to produce a grounded response. The example is associated with Lahore, and the prototype records configuration details using PostgreSQL. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 033, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 034: Text Chunking

**Record ID:** NOTE-034  
**Reviewer:** Bilal Ahmed  
**Team:** Data Systems Group  
**System:** LangChain  

This supplementary note revisits text chunking from the perspective of implementation and testing. Chunking divides long documents into smaller passages while preserving enough context for retrieval. Fixed-size, sentence-aware, and semantic strategies make different trade-offs. The example is associated with Islamabad, and the prototype records configuration details using Python. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 034, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 035: Vector Embeddings

**Record ID:** NOTE-035  
**Reviewer:** Sara Malik  
**Team:** Applied AI Centre  
**System:** Sentence Transformers  

This supplementary note revisits vector embeddings from the perspective of implementation and testing. An embedding model maps text into a numerical vector space. Similar meanings may occupy nearby regions, enabling semantic search beyond exact keyword matching. The example is associated with Karachi, and the prototype records configuration details using PyTorch. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 035, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 036: Metadata Filtering

**Record ID:** NOTE-036  
**Reviewer:** Hamza Qureshi  
**Team:** Digital Library Unit  
**System:** Qdrant  

This supplementary note revisits metadata filtering from the perspective of implementation and testing. Metadata adds structured context such as source, author, section, date, and access level. Filters can narrow retrieval before or after vector similarity search. The example is associated with Peshawar, and the prototype records configuration details using JSON. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 036, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 037: Evaluation and Retrieval Quality

**Record ID:** NOTE-037  
**Reviewer:** Noor Fatima  
**Team:** Research Quality Office  
**System:** Ragas  

This supplementary note revisits evaluation and retrieval quality from the perspective of implementation and testing. A retrieval system should be evaluated with representative questions, expected source passages, relevance judgments, and measures such as recall at k and mean reciprocal rank. The example is associated with Multan, and the prototype records configuration details using Pandas. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 037, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 038: Document Parsing

**Record ID:** NOTE-038  
**Reviewer:** Usman Tariq  
**Team:** Document Intelligence Team  
**System:** Docling  

This supplementary note revisits document parsing from the perspective of implementation and testing. Document parsing extracts text and structure from files. Headings, tables, lists, code blocks, and page boundaries can carry meaning that plain text extraction may lose. The example is associated with Faisalabad, and the prototype records configuration details using Apache Tika. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 038, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 039: Hybrid Search

**Record ID:** NOTE-039  
**Reviewer:** Hira Shah  
**Team:** Search Engineering Team  
**System:** Elasticsearch  

This supplementary note revisits hybrid search from the perspective of implementation and testing. Hybrid search combines lexical matching with vector similarity. Keyword search can preserve exact identifiers, while dense retrieval can find paraphrases and related concepts. The example is associated with Rawalpindi, and the prototype records configuration details using BM25. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 039, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 040: Responsible AI

**Record ID:** NOTE-040  
**Reviewer:** Zain Ali  
**Team:** Trustworthy Computing Forum  
**System:** NIST AI RMF  

This supplementary note revisits responsible ai from the perspective of implementation and testing. Responsible AI practice includes privacy, security, transparency, fairness, and human oversight. Teams should document limitations and test systems for unsafe or unsupported outputs. The example is associated with Quetta, and the prototype records configuration details using Audit Logs. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 040, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 041: Retrieval-Augmented Generation

**Record ID:** NOTE-041  
**Reviewer:** Amina Rahman  
**Team:** Open Knowledge Lab  
**System:** FAISS  

This supplementary note revisits retrieval-augmented generation from the perspective of implementation and testing. RAG combines retrieval with language generation. A retriever finds relevant passages, and a generator uses those passages to produce a grounded response. The example is associated with Lahore, and the prototype records configuration details using PostgreSQL. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 041, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 042: Text Chunking

**Record ID:** NOTE-042  
**Reviewer:** Bilal Ahmed  
**Team:** Data Systems Group  
**System:** LangChain  

This supplementary note revisits text chunking from the perspective of implementation and testing. Chunking divides long documents into smaller passages while preserving enough context for retrieval. Fixed-size, sentence-aware, and semantic strategies make different trade-offs. The example is associated with Islamabad, and the prototype records configuration details using Python. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 042, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 043: Vector Embeddings

**Record ID:** NOTE-043  
**Reviewer:** Sara Malik  
**Team:** Applied AI Centre  
**System:** Sentence Transformers  

This supplementary note revisits vector embeddings from the perspective of implementation and testing. An embedding model maps text into a numerical vector space. Similar meanings may occupy nearby regions, enabling semantic search beyond exact keyword matching. The example is associated with Karachi, and the prototype records configuration details using PyTorch. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 043, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 044: Metadata Filtering

**Record ID:** NOTE-044  
**Reviewer:** Hamza Qureshi  
**Team:** Digital Library Unit  
**System:** Qdrant  

This supplementary note revisits metadata filtering from the perspective of implementation and testing. Metadata adds structured context such as source, author, section, date, and access level. Filters can narrow retrieval before or after vector similarity search. The example is associated with Peshawar, and the prototype records configuration details using JSON. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 044, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 045: Evaluation and Retrieval Quality

**Record ID:** NOTE-045  
**Reviewer:** Noor Fatima  
**Team:** Research Quality Office  
**System:** Ragas  

This supplementary note revisits evaluation and retrieval quality from the perspective of implementation and testing. A retrieval system should be evaluated with representative questions, expected source passages, relevance judgments, and measures such as recall at k and mean reciprocal rank. The example is associated with Multan, and the prototype records configuration details using Pandas. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 045, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 046: Document Parsing

**Record ID:** NOTE-046  
**Reviewer:** Usman Tariq  
**Team:** Document Intelligence Team  
**System:** Docling  

This supplementary note revisits document parsing from the perspective of implementation and testing. Document parsing extracts text and structure from files. Headings, tables, lists, code blocks, and page boundaries can carry meaning that plain text extraction may lose. The example is associated with Faisalabad, and the prototype records configuration details using Apache Tika. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 046, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 047: Hybrid Search

**Record ID:** NOTE-047  
**Reviewer:** Hira Shah  
**Team:** Search Engineering Team  
**System:** Elasticsearch  

This supplementary note revisits hybrid search from the perspective of implementation and testing. Hybrid search combines lexical matching with vector similarity. Keyword search can preserve exact identifiers, while dense retrieval can find paraphrases and related concepts. The example is associated with Rawalpindi, and the prototype records configuration details using BM25. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 047, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 048: Responsible AI

**Record ID:** NOTE-048  
**Reviewer:** Zain Ali  
**Team:** Trustworthy Computing Forum  
**System:** NIST AI RMF  

This supplementary note revisits responsible ai from the perspective of implementation and testing. Responsible AI practice includes privacy, security, transparency, fairness, and human oversight. Teams should document limitations and test systems for unsafe or unsupported outputs. The example is associated with Quetta, and the prototype records configuration details using Audit Logs. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 048, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 049: Retrieval-Augmented Generation

**Record ID:** NOTE-049  
**Reviewer:** Amina Rahman  
**Team:** Open Knowledge Lab  
**System:** FAISS  

This supplementary note revisits retrieval-augmented generation from the perspective of implementation and testing. RAG combines retrieval with language generation. A retriever finds relevant passages, and a generator uses those passages to produce a grounded response. The example is associated with Lahore, and the prototype records configuration details using PostgreSQL. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 049, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 050: Text Chunking

**Record ID:** NOTE-050  
**Reviewer:** Bilal Ahmed  
**Team:** Data Systems Group  
**System:** LangChain  

This supplementary note revisits text chunking from the perspective of implementation and testing. Chunking divides long documents into smaller passages while preserving enough context for retrieval. Fixed-size, sentence-aware, and semantic strategies make different trade-offs. The example is associated with Islamabad, and the prototype records configuration details using Python. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 050, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 051: Vector Embeddings

**Record ID:** NOTE-051  
**Reviewer:** Sara Malik  
**Team:** Applied AI Centre  
**System:** Sentence Transformers  

This supplementary note revisits vector embeddings from the perspective of implementation and testing. An embedding model maps text into a numerical vector space. Similar meanings may occupy nearby regions, enabling semantic search beyond exact keyword matching. The example is associated with Karachi, and the prototype records configuration details using PyTorch. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 051, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 052: Metadata Filtering

**Record ID:** NOTE-052  
**Reviewer:** Hamza Qureshi  
**Team:** Digital Library Unit  
**System:** Qdrant  

This supplementary note revisits metadata filtering from the perspective of implementation and testing. Metadata adds structured context such as source, author, section, date, and access level. Filters can narrow retrieval before or after vector similarity search. The example is associated with Peshawar, and the prototype records configuration details using JSON. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 052, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 053: Evaluation and Retrieval Quality

**Record ID:** NOTE-053  
**Reviewer:** Noor Fatima  
**Team:** Research Quality Office  
**System:** Ragas  

This supplementary note revisits evaluation and retrieval quality from the perspective of implementation and testing. A retrieval system should be evaluated with representative questions, expected source passages, relevance judgments, and measures such as recall at k and mean reciprocal rank. The example is associated with Multan, and the prototype records configuration details using Pandas. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 053, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 054: Document Parsing

**Record ID:** NOTE-054  
**Reviewer:** Usman Tariq  
**Team:** Document Intelligence Team  
**System:** Docling  

This supplementary note revisits document parsing from the perspective of implementation and testing. Document parsing extracts text and structure from files. Headings, tables, lists, code blocks, and page boundaries can carry meaning that plain text extraction may lose. The example is associated with Faisalabad, and the prototype records configuration details using Apache Tika. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 054, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 055: Hybrid Search

**Record ID:** NOTE-055  
**Reviewer:** Hira Shah  
**Team:** Search Engineering Team  
**System:** Elasticsearch  

This supplementary note revisits hybrid search from the perspective of implementation and testing. Hybrid search combines lexical matching with vector similarity. Keyword search can preserve exact identifiers, while dense retrieval can find paraphrases and related concepts. The example is associated with Rawalpindi, and the prototype records configuration details using BM25. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 055, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 056: Responsible AI

**Record ID:** NOTE-056  
**Reviewer:** Zain Ali  
**Team:** Trustworthy Computing Forum  
**System:** NIST AI RMF  

This supplementary note revisits responsible ai from the perspective of implementation and testing. Responsible AI practice includes privacy, security, transparency, fairness, and human oversight. Teams should document limitations and test systems for unsafe or unsupported outputs. The example is associated with Quetta, and the prototype records configuration details using Audit Logs. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 056, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 057: Retrieval-Augmented Generation

**Record ID:** NOTE-057  
**Reviewer:** Amina Rahman  
**Team:** Open Knowledge Lab  
**System:** FAISS  

This supplementary note revisits retrieval-augmented generation from the perspective of implementation and testing. RAG combines retrieval with language generation. A retriever finds relevant passages, and a generator uses those passages to produce a grounded response. The example is associated with Lahore, and the prototype records configuration details using PostgreSQL. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 057, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 058: Text Chunking

**Record ID:** NOTE-058  
**Reviewer:** Bilal Ahmed  
**Team:** Data Systems Group  
**System:** LangChain  

This supplementary note revisits text chunking from the perspective of implementation and testing. Chunking divides long documents into smaller passages while preserving enough context for retrieval. Fixed-size, sentence-aware, and semantic strategies make different trade-offs. The example is associated with Islamabad, and the prototype records configuration details using Python. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 058, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 059: Vector Embeddings

**Record ID:** NOTE-059  
**Reviewer:** Sara Malik  
**Team:** Applied AI Centre  
**System:** Sentence Transformers  

This supplementary note revisits vector embeddings from the perspective of implementation and testing. An embedding model maps text into a numerical vector space. Similar meanings may occupy nearby regions, enabling semantic search beyond exact keyword matching. The example is associated with Karachi, and the prototype records configuration details using PyTorch. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 059, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 060: Metadata Filtering

**Record ID:** NOTE-060  
**Reviewer:** Hamza Qureshi  
**Team:** Digital Library Unit  
**System:** Qdrant  

This supplementary note revisits metadata filtering from the perspective of implementation and testing. Metadata adds structured context such as source, author, section, date, and access level. Filters can narrow retrieval before or after vector similarity search. The example is associated with Peshawar, and the prototype records configuration details using JSON. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 060, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 061: Evaluation and Retrieval Quality

**Record ID:** NOTE-061  
**Reviewer:** Noor Fatima  
**Team:** Research Quality Office  
**System:** Ragas  

This supplementary note revisits evaluation and retrieval quality from the perspective of implementation and testing. A retrieval system should be evaluated with representative questions, expected source passages, relevance judgments, and measures such as recall at k and mean reciprocal rank. The example is associated with Multan, and the prototype records configuration details using Pandas. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 061, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 062: Document Parsing

**Record ID:** NOTE-062  
**Reviewer:** Usman Tariq  
**Team:** Document Intelligence Team  
**System:** Docling  

This supplementary note revisits document parsing from the perspective of implementation and testing. Document parsing extracts text and structure from files. Headings, tables, lists, code blocks, and page boundaries can carry meaning that plain text extraction may lose. The example is associated with Faisalabad, and the prototype records configuration details using Apache Tika. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 062, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 063: Hybrid Search

**Record ID:** NOTE-063  
**Reviewer:** Hira Shah  
**Team:** Search Engineering Team  
**System:** Elasticsearch  

This supplementary note revisits hybrid search from the perspective of implementation and testing. Hybrid search combines lexical matching with vector similarity. Keyword search can preserve exact identifiers, while dense retrieval can find paraphrases and related concepts. The example is associated with Rawalpindi, and the prototype records configuration details using BM25. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 063, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 064: Responsible AI

**Record ID:** NOTE-064  
**Reviewer:** Zain Ali  
**Team:** Trustworthy Computing Forum  
**System:** NIST AI RMF  

This supplementary note revisits responsible ai from the perspective of implementation and testing. Responsible AI practice includes privacy, security, transparency, fairness, and human oversight. Teams should document limitations and test systems for unsafe or unsupported outputs. The example is associated with Quetta, and the prototype records configuration details using Audit Logs. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 064, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 065: Retrieval-Augmented Generation

**Record ID:** NOTE-065  
**Reviewer:** Amina Rahman  
**Team:** Open Knowledge Lab  
**System:** FAISS  

This supplementary note revisits retrieval-augmented generation from the perspective of implementation and testing. RAG combines retrieval with language generation. A retriever finds relevant passages, and a generator uses those passages to produce a grounded response. The example is associated with Lahore, and the prototype records configuration details using PostgreSQL. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 065, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 066: Text Chunking

**Record ID:** NOTE-066  
**Reviewer:** Bilal Ahmed  
**Team:** Data Systems Group  
**System:** LangChain  

This supplementary note revisits text chunking from the perspective of implementation and testing. Chunking divides long documents into smaller passages while preserving enough context for retrieval. Fixed-size, sentence-aware, and semantic strategies make different trade-offs. The example is associated with Islamabad, and the prototype records configuration details using Python. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 066, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 067: Vector Embeddings

**Record ID:** NOTE-067  
**Reviewer:** Sara Malik  
**Team:** Applied AI Centre  
**System:** Sentence Transformers  

This supplementary note revisits vector embeddings from the perspective of implementation and testing. An embedding model maps text into a numerical vector space. Similar meanings may occupy nearby regions, enabling semantic search beyond exact keyword matching. The example is associated with Karachi, and the prototype records configuration details using PyTorch. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 067, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 068: Metadata Filtering

**Record ID:** NOTE-068  
**Reviewer:** Hamza Qureshi  
**Team:** Digital Library Unit  
**System:** Qdrant  

This supplementary note revisits metadata filtering from the perspective of implementation and testing. Metadata adds structured context such as source, author, section, date, and access level. Filters can narrow retrieval before or after vector similarity search. The example is associated with Peshawar, and the prototype records configuration details using JSON. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 068, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 069: Evaluation and Retrieval Quality

**Record ID:** NOTE-069  
**Reviewer:** Noor Fatima  
**Team:** Research Quality Office  
**System:** Ragas  

This supplementary note revisits evaluation and retrieval quality from the perspective of implementation and testing. A retrieval system should be evaluated with representative questions, expected source passages, relevance judgments, and measures such as recall at k and mean reciprocal rank. The example is associated with Multan, and the prototype records configuration details using Pandas. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 069, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 070: Document Parsing

**Record ID:** NOTE-070  
**Reviewer:** Usman Tariq  
**Team:** Document Intelligence Team  
**System:** Docling  

This supplementary note revisits document parsing from the perspective of implementation and testing. Document parsing extracts text and structure from files. Headings, tables, lists, code blocks, and page boundaries can carry meaning that plain text extraction may lose. The example is associated with Faisalabad, and the prototype records configuration details using Apache Tika. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 070, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 071: Hybrid Search

**Record ID:** NOTE-071  
**Reviewer:** Hira Shah  
**Team:** Search Engineering Team  
**System:** Elasticsearch  

This supplementary note revisits hybrid search from the perspective of implementation and testing. Hybrid search combines lexical matching with vector similarity. Keyword search can preserve exact identifiers, while dense retrieval can find paraphrases and related concepts. The example is associated with Rawalpindi, and the prototype records configuration details using BM25. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 071, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 072: Responsible AI

**Record ID:** NOTE-072  
**Reviewer:** Zain Ali  
**Team:** Trustworthy Computing Forum  
**System:** NIST AI RMF  

This supplementary note revisits responsible ai from the perspective of implementation and testing. Responsible AI practice includes privacy, security, transparency, fairness, and human oversight. Teams should document limitations and test systems for unsafe or unsupported outputs. The example is associated with Quetta, and the prototype records configuration details using Audit Logs. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 072, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 073: Retrieval-Augmented Generation

**Record ID:** NOTE-073  
**Reviewer:** Amina Rahman  
**Team:** Open Knowledge Lab  
**System:** FAISS  

This supplementary note revisits retrieval-augmented generation from the perspective of implementation and testing. RAG combines retrieval with language generation. A retriever finds relevant passages, and a generator uses those passages to produce a grounded response. The example is associated with Lahore, and the prototype records configuration details using PostgreSQL. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 073, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 074: Text Chunking

**Record ID:** NOTE-074  
**Reviewer:** Bilal Ahmed  
**Team:** Data Systems Group  
**System:** LangChain  

This supplementary note revisits text chunking from the perspective of implementation and testing. Chunking divides long documents into smaller passages while preserving enough context for retrieval. Fixed-size, sentence-aware, and semantic strategies make different trade-offs. The example is associated with Islamabad, and the prototype records configuration details using Python. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 074, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 075: Vector Embeddings

**Record ID:** NOTE-075  
**Reviewer:** Sara Malik  
**Team:** Applied AI Centre  
**System:** Sentence Transformers  

This supplementary note revisits vector embeddings from the perspective of implementation and testing. An embedding model maps text into a numerical vector space. Similar meanings may occupy nearby regions, enabling semantic search beyond exact keyword matching. The example is associated with Karachi, and the prototype records configuration details using PyTorch. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 075, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 076: Metadata Filtering

**Record ID:** NOTE-076  
**Reviewer:** Hamza Qureshi  
**Team:** Digital Library Unit  
**System:** Qdrant  

This supplementary note revisits metadata filtering from the perspective of implementation and testing. Metadata adds structured context such as source, author, section, date, and access level. Filters can narrow retrieval before or after vector similarity search. The example is associated with Peshawar, and the prototype records configuration details using JSON. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 076, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 077: Evaluation and Retrieval Quality

**Record ID:** NOTE-077  
**Reviewer:** Noor Fatima  
**Team:** Research Quality Office  
**System:** Ragas  

This supplementary note revisits evaluation and retrieval quality from the perspective of implementation and testing. A retrieval system should be evaluated with representative questions, expected source passages, relevance judgments, and measures such as recall at k and mean reciprocal rank. The example is associated with Multan, and the prototype records configuration details using Pandas. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 077, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 078: Document Parsing

**Record ID:** NOTE-078  
**Reviewer:** Usman Tariq  
**Team:** Document Intelligence Team  
**System:** Docling  

This supplementary note revisits document parsing from the perspective of implementation and testing. Document parsing extracts text and structure from files. Headings, tables, lists, code blocks, and page boundaries can carry meaning that plain text extraction may lose. The example is associated with Faisalabad, and the prototype records configuration details using Apache Tika. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 078, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 079: Hybrid Search

**Record ID:** NOTE-079  
**Reviewer:** Hira Shah  
**Team:** Search Engineering Team  
**System:** Elasticsearch  

This supplementary note revisits hybrid search from the perspective of implementation and testing. Hybrid search combines lexical matching with vector similarity. Keyword search can preserve exact identifiers, while dense retrieval can find paraphrases and related concepts. The example is associated with Rawalpindi, and the prototype records configuration details using BM25. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 079, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?

### Supplementary Note 080: Responsible AI

**Record ID:** NOTE-080  
**Reviewer:** Zain Ali  
**Team:** Trustworthy Computing Forum  
**System:** NIST AI RMF  

This supplementary note revisits responsible ai from the perspective of implementation and testing. Responsible AI practice includes privacy, security, transparency, fairness, and human oversight. Teams should document limitations and test systems for unsafe or unsupported outputs. The example is associated with Quetta, and the prototype records configuration details using Audit Logs. These names are synthetic corpus entities intended to test named-entity handling.

For experiment 080, the developer should create a small input set, run the selected operation, save the output, and compare it with an expected result. The test should include a short passage, a long passage, a passage with a proper noun, and a passage containing a date or identifier.

**Implementation checklist**

- Confirm that the source file can be opened using UTF-8 encoding.
- Preserve headings and paragraph boundaries where possible.
- Record the chunk index and character offsets.
- Include overlap only when it improves continuity.
- Keep metadata separate from the embedded text unless the design explicitly combines them.
- Verify that repeated runs produce stable document identifiers.

**Discussion prompt:** What evidence would demonstrate that the selected chunking strategy is working?
