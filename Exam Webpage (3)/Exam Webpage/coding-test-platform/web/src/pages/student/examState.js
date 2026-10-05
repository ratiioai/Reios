/**
 * Exam-runner constants and helpers shared by the exam page and its panels.
 */
export const LANG_LABELS = {
  python: "Python 3", cpp: "C++17", c: "C", java: "Java", javascript: "JavaScript (Node)",
};

export const DEFAULT_CODE = {
  python: "# Read input from stdin and print the answer\n",
  cpp: "#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n",
  c: "#include <stdio.h>\n\nint main() {\n    \n    return 0;\n}\n",
  java:
    "import java.util.*;\n\npublic class Main {\n    public static void main(String[] args) {\n" +
    "        Scanner sc = new Scanner(System.in);\n        \n    }\n}\n",
  javascript: "const lines = require('fs').readFileSync(0, 'utf8').trim().split('\\n');\n",
};

export const VIOLATION_TEXT = {
  fullscreen_exit: "You left fullscreen mode",
  tab_switch: "You switched to another tab or window",
  window_blur: "The exam window lost focus",
  paste_attempt: "Pasting is not allowed",
  copy_attempt: "Copying is not allowed",
  right_click: "Right-click is disabled",
  devtools_open: "Developer tools are not allowed",
  keyboard_shortcut: "That keyboard shortcut is blocked",
  print_screen: "Screenshots are not allowed",
};

export function isFullscreen() {
  return !!(document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement);
}

export async function enterFullscreen() {
  const el = document.documentElement;
  const req = el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen;
  if (!req) throw new Error("Your browser doesn't support fullscreen. Use the latest Chrome, Edge or Firefox.");
  await req.call(el);
}

export function exitFullscreen() {
  if (!isFullscreen()) return;
  const fn = document.exitFullscreen || document.webkitExitFullscreen;
  if (fn) fn.call(document).catch(() => {});
}

/** Build the initial per-item answer state from the paper the server returned. */
export function buildAnswerState(paper) {
  const mcq = {};
  const code = {};
  paper.items.forEach((item) => {
    if (item.type === "mcq") {
      mcq[item.item_id] = {
        selected: item.answer.selected.slice(),
        review: item.answer.marked_for_review,
      };
    } else {
      const language = item.answer ? item.answer.language : paper.exam.allowed_languages[0];
      code[item.item_id] = {
        language,
        drafts: item.answer ? { [item.answer.language]: item.answer.code } : {},
        dirty: false,
        // Starter code is pre-filled, so "has text" alone must not count as answered.
        touched: !!(item.answer && item.answer.code.trim()),
        result:
          item.answer && item.answer.graded
            ? { passed_tests: item.answer.passed_tests, total_tests: item.answer.total_tests }
            : null,
      };
    }
  });
  return { mcq, code };
}

export function isAnswered(item, mcq, code) {
  if (item.type === "mcq") return (mcq[item.item_id]?.selected.length || 0) > 0;
  return !!code[item.item_id]?.touched;
}
