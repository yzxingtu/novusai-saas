import { describe, expect, it } from 'vitest';

import {
  formatStarterQuestionsInput,
  normalizeStarterQuestions,
  parseStarterQuestionsInput,
} from '../ai-starter-questions';

describe('ai-starter-questions', () => {
  it('normalizes string arrays for display', () => {
    expect(
      normalizeStarterQuestions([
        '  First question  ',
        '',
        'Second question',
        123,
      ]),
    ).toEqual(['First question', 'Second question']);
  });

  it('parses JSON arrays and single JSON strings', () => {
    expect(parseStarterQuestionsInput('["Question 1", "Question 2"]')).toEqual([
      'Question 1',
      'Question 2',
    ]);
    expect(parseStarterQuestionsInput('"Single question"')).toEqual([
      'Single question',
    ]);
  });

  it('parses one question per line and strips common list prefixes', () => {
    expect(
      parseStarterQuestionsInput(`
1. First question
- Second question
* Third question
      `),
    ).toEqual(['First question', 'Second question', 'Third question']);
  });

  it('formats stored arrays as one question per line', () => {
    expect(formatStarterQuestionsInput(['Question 1', 'Question 2'])).toBe(
      'Question 1\nQuestion 2',
    );
  });
});
