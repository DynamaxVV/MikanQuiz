const assert = require("assert");
const { DEFAULT_SETTINGS, gradeQuestions, selectQuestions, validateQuestion, validateSettings } = require("../lib/quiz");

const questions = [{ _id: "q1", text: "题目", difficulty: 3, options: ["甲", "乙", "丙", "丁"], answer: "B", explanations: { A: "A 解析", B: "B 解析", C: "C 解析", D: "D 解析" } }];
const result = gradeQuestions(questions, { q1: "B" });
assert.deepStrictEqual({ score: result.score, correctCount: result.correctCount, selected: result.details[0].selected, explanation: result.details[0].selectedExplanation }, { score: 100, correctCount: 1, selected: "B", explanation: "B 解析" });
assert.strictEqual(validateQuestion(questions[0]), "");
assert.strictEqual(validateQuestion({ _id: "new", text: "新题", difficulty: 1, options: ["A", "B", "C", "D"], answer: "A", explanation: "统一解析" }), "");
assert.strictEqual(gradeQuestions([{ _id: "new", text: "新题", difficulty: 1, options: ["A", "B", "C", "D"], answer: "A", explanation: "统一解析" }], { new: "B" }).details[0].selectedExplanation, "统一解析");
assert.ok(validateQuestion({ ...questions[0], answer: "Z" }));
assert.strictEqual(validateSettings(DEFAULT_SETTINGS), "");
assert.strictEqual(selectQuestions(questions, { ...DEFAULT_SETTINGS, questionCount: 1 }, "beginner").length, 1);
const mixedQuestions = [1, 2, 3, 4, 5].map((difficulty) => ({ ...questions[0], _id: `q${difficulty}`, difficulty }));
const fixedSettings = { questionCount: 1, modes: { beginner: [0, 0, 100, 0, 0], proficient: [0, 0, 100, 0, 0], challenge: [0, 0, 100, 0, 0] } };
assert.strictEqual(selectQuestions(mixedQuestions, fixedSettings, "beginner")[0].difficulty, 3);
console.log("cloud quiz grading checks passed");
