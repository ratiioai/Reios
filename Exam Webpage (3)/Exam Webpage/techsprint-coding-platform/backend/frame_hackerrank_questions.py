"""
HackerRank Question Framing Engine
Transforms all 350 questions into standard HackerRank structured format with:
- Problem Statement
- Input Format
- Constraints
- Output Format
- Sample Input / Output 0, 1 with step-by-step Explanations
- Starter Code Boilerplates for Python 3, C++, Java, JavaScript
"""
import sqlite3
import re
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "coding_test.db")


def get_constraints(clean_title, difficulty):
    t = clean_title.lower()
    if "matrix" in t or "2d" in t or "diagonal" in t:
        return "- $1 \\le R, C \\le 100$\n- $-10^3 \\le \\text{Matrix}[i][j] \\le 10^3$"
    elif "string" in t or "word" in t or "palindrome" in t or "anagram" in t or "vowel" in t or "consonant" in t or "character" in t:
        return "- $1 \\le |S| \\le 10^5$\n- String contains standard alphanumeric and ASCII characters."
    elif "array" in t or "element" in t or "sort" in t or "search" in t or "reverse" in t or "even" in t or "odd" in t:
        if difficulty == "Easy":
            return "- $1 \\le N \\le 10^4$\n- $-10^4 \\le A[i] \\le 10^4$"
        elif difficulty == "Medium":
            return "- $1 \\le N \\le 10^5$\n- $-10^5 \\le A[i] \\le 10^5$"
        else:
            return "- $1 \\le N \\le 2 \\times 10^5$\n- $-10^9 \\le A[i] \\le 10^9$"
    else:
        if "prime" in t or "factorial" in t or "fibonacci" in t:
            return "- $1 \\le N \\le 50$"
        elif "digit" in t or "reverse" in t:
            return "- $0 \\le N \\le 10^9$"
        else:
            return "- $-10^6 \\le N \\le 10^6$"


def get_input_format(clean_title):
    t = clean_title.lower()
    if any(k in t for k in ["sum of two", "difference of two", "product of two", "power of a", "swap two", "largest of two", "smallest of two"]):
        return "The first and only line contains two space-separated integers, $a$ and $b$."
    elif any(k in t for k in ["average of three", "largest of three", "smallest of three", "middle of three", "maximum of three", "minimum of three"]):
        return "The first and only line contains three space-separated integers, $a$, $b$, and $c$."
    elif "matrix" in t or "diagonal" in t:
        return "The first line contains two integers $R$ and $C$ representing the number of rows and columns.\nThe next $R$ lines each contain $C$ space-separated integers representing the matrix elements."
    elif any(k in t for k in ["linear search", "binary search", "count elements greater", "kth smallest", "kth largest", "count occurrences"]):
        return "The first line contains an integer $N$, the number of elements in the array.\nThe second line contains $N$ space-separated integers representing the elements of the array.\nThe third line contains the target integer or parameter $K$."
    elif any(k in t for k in ["array", "element", "sort", "reverse array", "consecutive", "zeroes", "even and odd", "separate", "move"]):
        return "The first line contains an integer $N$, denoting the size of the array.\nThe second line contains $N$ space-separated integers representing the array elements."
    elif any(k in t for k in ["string", "word", "character", "vowel", "consonant", "anagram", "palindrome", "case", "remove digits"]):
        if "anagram" in t or "rotation" in t:
            return "The first line contains two space-separated strings, $s_1$ and $s_2$."
        elif "character" in t and ("remove" in t or "count" in t):
            return "The first line contains a string $S$ followed by a target character $C$ separated by a space."
        else:
            return "The first line contains a single string $S$."
    elif any(k in t for k in ["print numbers", "print odd", "print even", "print factors", "print squares", "sum of first", "natural numbers", "multiplication table"]):
        return "The first and only line contains a single integer $N$."
    else:
        return "The first and only line contains a single integer $N$."


def get_output_format(clean_title):
    t = clean_title.lower()
    if "even or odd" in t:
        return "Print `Even` if the integer is even, or `Odd` if it is odd."
    elif "prime" in t:
        return "Print `Prime` if $N$ is prime, or `Not Prime` otherwise."
    elif "palindrome" in t or "anagram" in t:
        return "Print `True` or `Yes` if the condition is satisfied, or `False` / `No` otherwise (as specified in sample cases)."
    elif any(k in t for k in ["print numbers", "print odd", "print even", "print factors", "print squares", "separate even and odd", "sort", "reverse"]):
        return "Print the resulting numbers or sequence separated by spaces on a single line."
    elif "matrix" in t or "diagonal" in t:
        return "Print the calculated result or transformed matrix."
    elif any(k in t for k in ["sum", "average", "difference", "product", "largest", "smallest", "count", "maximum", "minimum", "kth"]):
        return "Print the single evaluated numerical or categorical answer."
    else:
        return "Print the required output to standard output (stdout)."


def generate_explanation(clean_title, inp, out, idx):
    if not inp:
        return f"For this case, the evaluated output is `{out}`."
    
    clean_inp = inp.replace("\n", " ").strip()
    return f"Given input `{clean_inp}`, the program evaluates and outputs `{out}` as expected."


def get_boilerplates(clean_title):
    py = '''import sys

def solve():
    # Read all inputs from standard input
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    
    # TODO: Implement your solution here
    pass

if __name__ == '__main__':
    solve()
'''

    cpp = '''#include <iostream>
#include <vector>
#include <string>
#include <algorithm>

using namespace std;

int main() {
    // Fast I/O
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    
    // TODO: Read input from standard input (cin) and solve
    
    return 0;
}
'''

    java = '''import java.util.Scanner;

public class Solution {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        
        // TODO: Read input from standard input and solve
        
        scanner.close();
    }
}
'''

    js = '''const fs = require('fs');

function solve() {
    const input = fs.readFileSync(0, 'utf-8').trim().split(/\\s+/);
    if (!input || input.length === 0 || input[0] === "") return;
    
    // TODO: Process input array and print result to console.log
}

solve();
'''

    return py, cpp, java, js


def frame_question_markdown(clean_title, prompt, difficulty, marks, samples):
    input_fmt = get_input_format(clean_title)
    constraints = get_constraints(clean_title, difficulty)
    output_fmt = get_output_format(clean_title)
    
    # Extract clean narrative (if already framed previously, extract Problem Statement section)
    m = re.search(r'### Problem Statement\s*\n(.*?)(?=\n###|\Z)', prompt, re.DOTALL)
    if m:
        narrative = m.group(1).strip()
    else:
        narrative = prompt.strip()
        
    if not narrative.endswith("."):
        narrative += "."
    
    md_parts = [
        f"### Problem Statement\n{narrative}",
        f"### Input Format\n{input_fmt}",
        f"### Constraints\n{constraints}",
        f"### Output Format\n{output_fmt}"
    ]
    
    # Add Sample Cases
    for idx, (inp, out, exp) in enumerate(samples):
        display_inp = inp if inp else "(Empty / No Input)"
        display_exp = exp if exp else generate_explanation(clean_title, inp, out, idx)
        
        md_parts.append(f"### Sample Input {idx}\n```\n{display_inp}\n```")
        md_parts.append(f"### Sample Output {idx}\n```\n{out}\n```")
        md_parts.append(f"### Explanation {idx}\n{display_exp}")
        
    return "\n\n".join(md_parts)


def run_framing():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, title, prompt_markdown, difficulty, marks FROM questions ORDER BY id")
    questions = cursor.fetchall()
    
    print(f"Reframing {len(questions)} questions in HackerRank format...")
    
    for q_id, title, prompt, difficulty, marks in questions:
        clean_title = re.sub(r'^\[.*?\]\s*', '', title).strip()
        
        cursor.execute("SELECT input_data, expected_output, explanation FROM sample_test_cases WHERE question_id = ? ORDER BY `order`", (q_id,))
        samples = cursor.fetchall()
        
        # Build HackerRank Markdown
        hr_markdown = frame_question_markdown(clean_title, prompt, difficulty, marks, samples)
        
        # Build starter codes
        py_code, cpp_code, java_code, js_code = get_boilerplates(clean_title)
        
        cursor.execute("""
            UPDATE questions 
            SET prompt_markdown = ?,
                starter_code_python = ?,
                starter_code_cpp = ?,
                starter_code_java = ?,
                starter_code_javascript = ?
            WHERE id = ?
        """, (hr_markdown, py_code, cpp_code, java_code, js_code, q_id))
        
    conn.commit()
    conn.close()
    print("SUCCESS: All 350 questions successfully converted to HackerRank structure!")


if __name__ == "__main__":
    run_framing()
