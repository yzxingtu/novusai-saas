export function normalizeStarterQuestions(
  input: null | undefined | unknown[],
): string[] {
  if (!Array.isArray(input)) {
    return [];
  }

  return input
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function stripStarterQuestionPrefix(line: string): string {
  return line
    .replace(/^[-*]\s+/, '')
    .replace(/^\d+[.)]\s+/, '')
    .trim();
}

export function parseStarterQuestionsInput(
  text: null | string | undefined,
): null | string[] {
  const raw = text?.trim() ?? '';
  if (!raw || raw === '[]') {
    return null;
  }

  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed === 'string') {
      const single = parsed.trim();
      return single ? [single] : null;
    }
    const normalized = normalizeStarterQuestions(parsed);
    return normalized.length > 0 ? normalized : null;
  } catch {
    const normalized = raw
      .split(/\r?\n/u)
      .map((line) => stripStarterQuestionPrefix(line))
      .filter((line) => line.length > 0);
    return normalized.length > 0 ? normalized : null;
  }
}

export function formatStarterQuestionsInput(
  input: null | undefined | unknown[],
): string {
  return normalizeStarterQuestions(input).join('\n');
}
