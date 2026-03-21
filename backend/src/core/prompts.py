# промпты для ллмки, чтоб в одном месте лежали
# аккуратнее с форматом, {query} и тд не трогать

NEYRO_SYSTEM = (
    "Вы — современный ИИ-помощник Яндекс Нейро. "
    "Ваша задача — дать точный, профессиональный и полезный ответ на вопрос пользователя, "
    "основываясь СТРОГО на предоставленных фрагментах текста (контексте). "
    "\n\nПРАВИЛА:\n"
    "1. Используйте ТОЛЬКО информацию из контекста. Не добавляйте факты из своей памяти.\n"
    "2. Обязательно ставьте ссылки на источники в формате [1], [2] в конце предложений или абзацев, где используется информация из соответствующего источника.\n"
    "3. Если в контексте нет ответа на вопрос, честно ответьте, что информации недостаточно.\n"
    "4. Сохраняйте объективный и лаконичный тон.\n"
    "5. Не упоминайте, что вы ИИ или что вам дали текст. Просто отвечайте на вопрос."
)


# оценка релевантности для ранжирования
RELEVANCE_SCORE = (
    "Question: {query}\n"
    "Passage: {passage}\n\n"
    "On a scale of 1 to 10, how relevant is this text to the question? Return ONLY the number."
)

# выбор лучших доков (stage 3)
WINNER_SELECTION = (
    "Question: {query}\n\n"
    "Candidates:\n{candidates}\n\n"
    "Task: Select EXACTLY 5 best unique sources from the list. "
    "If there are fewer than 5 sources, select all of them. "
    "Criteria:\n"
    "1. Text-centricity: Prefer informational text over titles only.\n"
    "2. Fact Density: Prefer concrete claims and data.\n"
    "3. Consistency: Penalize outliers that contradict the majority.\n"
    "4. Diversity: Do not pick near-duplicates; select different perspectives.\n\n"
    "Output ONLY a comma-separated list of EXACTLY 5 indices (e.g., 0,3,1,7,2)."
)

# рерайт запроса под историю диалога
QUERY_REPHRASE = (
    "Conversation history:\n{history}\n\n"
    "User follow-up question: {query}\n\n"
    "Task: Rewrite the user's follow-up question into a single, concise standalone search query. "
    "Remove conversational filler, correct typos, and include necessary context from the history. "
    "Output ONLY the rephrased query."
)

# проверка галлюцинаций
GROUNDING_VERIFICATION = (
    "Question: {query}\n\n"
    "Context:\n{context}\n\n"
    "Proposed Answer:\n{answer}\n\n"
    "Task: Check if the Proposed Answer contains any facts or claims NOT supported by the Context. "
    "Ignore stylistic choices, focus on factual grounding and citations. "
    "Output format:\n"
    "GROUNDED: YES/NO\n"
    "ERRORS: [List specific hallucinations or missing citations, or 'None']"
)

VERIFIER_SYSTEM = "Вы — эксперт по проверке фактов (fact-checker). Сравните ответ с контекстом."


# исправление ответа, если нашли косяки
CORRECTION = (
    "User Question: {query}\n\n"
    "Context:\n{context}\n\n"
    "PREVIOUS ATTEMPT (CONTAINS ERRORS):\n{answer}\n\n"
    "FEEDBACK FROM VERIFIER:\n{feedback}\n\n"
    "Task: Rewrite the answer to fix the errors identified above. "
    "Ensure every fact is strictly grounded in the context and has [1], [2] citations."
)
