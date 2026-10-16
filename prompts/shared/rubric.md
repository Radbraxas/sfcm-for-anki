## What makes a good card

These rules adapt Piotr Wozniak's "20 rules of formulating knowledge" for Anki.

1. **One fact per card.** Each card tests exactly one piece of knowledge. Split lists, comparisons and multi-part ideas into several cards.
2. **One correct answer.** A reader who knows the material can give only one answer. Add context to the question when the answer could be ambiguous.
3. **Short answers.** Aim for under 15 words on the answer side. Put explanation in the "why" field, not the answer.
4. **No yes/no questions.** Ask "which", "why", "how" or "what" instead.
5. **Prefer understanding over trivia.** Cover the ideas the source treats as important first: causes, mechanisms, consequences and distinctions between similar concepts. Skip incidental details (page numbers, anecdotes, author names) unless the source is about them.
6. **Cloze cards delete the meaningful part.** Delete key terms, numbers or relationships, never filler words. Use {{c1::...}} for one card; use c2, c3 only for deletions that should be separate cards. A hint goes after a second `::`, as in {{c1::mitochondria::organelle}}.
7. **Keep the source's facts.** Do not add claims the source does not support. If the source is wrong or unclear, follow it anyway and do not invent corrections.
8. **No duplicates.** Do not make two cards that test the same fact in different words.
9. **Plain text only.** Use **bold** for the key term, `code` for code and \( ... \) for math. No HTML and no Markdown headings.
10. **Pick the note type that fits.**
    - `basic`: a question with a short answer.
    - `basic_reversed`: a term and definition that should be learned in both directions (vocabulary, symbols).
    - `basic_optional_reversed`: like reversed, but only some learners need the reverse card. Use it rarely.
    - `basic_type_in`: answers that must be spelled exactly (a word in a foreign language, a formula, a command).
    - `cloze`: a fact that reads naturally as a sentence, or a sequence or list where position matters.
