# Prompt changelog

Prompts are versioned independently of the app. Cards record the version that made them (`card_generation@1.0.0`).
Never edit a released version. Copy the folder to a new version, change the copy, and add an entry here with the eval score change (`just eval`).

## card_generation

### 1.0.0
- First version: rubric based on the 20 rules of formulating knowledge, all five generatable note types, structured JSON output, prompt-injection guard for source text.

## eval_judge

### 1.0.0
- First version: scores faithfulness, atomicity and clarity from 1 to 5 per card.
