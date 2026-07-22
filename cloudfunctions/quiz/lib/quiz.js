const OPTION_KEYS = ["A", "B", "C", "D"];
const DEFAULT_SETTINGS = {
  questionCount: 10,
  modes: {
    beginner: [65, 25, 10, 0, 0],
    proficient: [15, 25, 30, 20, 10],
    challenge: [0, 10, 20, 30, 40],
  },
  fontPresets: [],
};

function sanitizeQuestion(question) {
  return { _id: question._id, text: question.text, imageFileID: question.imageFileID || "", difficulty: question.difficulty || 1, options: question.options };
}

function validateQuestion(question) {
  if (!question || typeof question.text !== "string" || !Array.isArray(question.options)) return "题目格式不正确";
  if (!question.text.trim() || question.options.length !== 4 || question.options.some((item) => typeof item !== "string" || !item.trim())) return "请填写题目和选项";
  if (!Number.isInteger(question.difficulty) || question.difficulty < 1 || question.difficulty > 5) return "请选择 1 到 5 星难度";
  const hasUnifiedExplanation = typeof question.explanation === "string" && question.explanation.trim();
  const hasLegacyExplanations = question.explanations && OPTION_KEYS.every((key) => typeof question.explanations[key] === "string" && question.explanations[key].trim());
  if (!OPTION_KEYS.includes(question.answer) || (!hasUnifiedExplanation && !hasLegacyExplanations)) return "请填写题目解析";
  return "";
}

function gradeQuestions(questions, answers) {
  const details = questions.map((question) => ({
    ...sanitizeQuestion(question), answer: question.answer,
    selected: answers[question._id] || "", selectedExplanation: question.explanation || (question.explanations || {})[answers[question._id]] || "未选择选项，无对应解析。", isCorrect: answers[question._id] === question.answer,
  }));
  const correctCount = details.filter((item) => item.isCorrect).length;
  return { total: questions.length, correctCount, score: questions.length ? Math.round((correctCount / questions.length) * 100) : 0, details };
}

function validateSettings(settings) {
  if (!settings || !Number.isInteger(settings.questionCount) || settings.questionCount < 1 || settings.questionCount > 50) return "题目数量应为 1 到 50";
  const modes = ["beginner", "proficient", "challenge"];
  if (!settings.modes || modes.some((mode) => !Array.isArray(settings.modes[mode]) || settings.modes[mode].length !== 5 || settings.modes[mode].some((weight) => !Number.isInteger(weight) || weight < 0) || !settings.modes[mode].some((weight) => weight > 0))) return "每种难度至少设置一个大于 0 的星级比重";
  return "";
}

function shuffled(items) {
  const result = [...items];
  for (let index = result.length - 1; index > 0; index -= 1) {
    const randomIndex = Math.floor(Math.random() * (index + 1));
    [result[index], result[randomIndex]] = [result[randomIndex], result[index]];
  }
  return result;
}

function selectQuestions(questions, settings, mode) {
  const weights = settings.modes[mode] || DEFAULT_SETTINGS.modes.beginner;
  const available = shuffled(questions);
  const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);
  const picked = [];
  while (available.length && picked.length < settings.questionCount) {
    let cursor = Math.random() * totalWeight;
    const difficulty = weights.findIndex((weight) => ((cursor -= weight) < 0)) + 1;
    const matchIndex = available.findIndex((item) => (item.difficulty || 1) === difficulty);
    picked.push(available.splice(matchIndex >= 0 ? matchIndex : 0, 1)[0]);
  }
  return picked;
}

module.exports = { DEFAULT_SETTINGS, gradeQuestions, sanitizeQuestion, selectQuestions, validateQuestion, validateSettings };
