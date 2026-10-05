"""
Optimized Master Test Case Generator and Populator for all 350 Questions.
Uses bulk database operations and fast solver logic.
"""
import sys
import os
import re
import math

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models import Question, SampleTestCase, HiddenTestCase

def solve_fast(title, prompt, stdin_text):
    t = re.sub(r'^\[.*?\]\s*', '', title).lower().strip()
    tokens = stdin_text.strip().split()
    if not tokens:
        return ""
        
    try:
        # Arithmetic / Two numbers
        if "sum of two numbers" in t:
            return str(int(tokens[0]) + int(tokens[1]))
        if "difference of two" in t:
            return str(int(tokens[0]) - int(tokens[1]))
        if "product of two" in t or "multiply two" in t:
            return str(int(tokens[0]) * int(tokens[1]))
        if "average of three" in t:
            avg = (int(tokens[0]) + int(tokens[1]) + int(tokens[2])) / 3
            return f"{int(avg)}" if avg.is_integer() else f"{avg:.2f}"
        if "swap two" in t:
            return f"{tokens[1]} {tokens[0]}"
        if "power of a number" in t or "a^b" in t:
            return str(int(tokens[0]) ** int(tokens[1]))

        # Comparisons
        if "largest of three" in t or "maximum of three" in t:
            return str(max(int(tokens[0]), int(tokens[1]), int(tokens[2])))
        if "smallest of three" in t or "minimum of three" in t:
            return str(min(int(tokens[0]), int(tokens[1]), int(tokens[2])))
        if "middle of three" in t:
            return str(sorted([int(tokens[0]), int(tokens[1]), int(tokens[2])])[1])
        if "largest of two" in t or "maximum of two" in t:
            return str(max(int(tokens[0]), int(tokens[1])))
        if "smallest of two" in t or "minimum of two" in t:
            return str(min(int(tokens[0]), int(tokens[1])))

        # Logic checks
        if "even or odd" in t or "even/odd" in t or "check even" in t:
            return "Even" if int(tokens[0]) % 2 == 0 else "Odd"
        if "positive, negative" in t or "positive or negative" in t:
            n = int(tokens[0])
            return "Positive" if n > 0 else ("Negative" if n < 0 else "Zero")
        if "check leap year" in t or "leap year" in t:
            y = int(tokens[0])
            return "YES" if (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0) else "NO"
        if "check prime" in t or "prime number" in t:
            n = int(tokens[0])
            if n <= 1: return "NO"
            for i in range(2, int(math.isqrt(n)) + 1):
                if n % i == 0: return "NO"
            return "YES"
        if "check divisibility by 10 or 5" in t:
            n = int(tokens[0])
            return "YES" if (n % 10 == 0 or n % 5 == 0) else "NO"
        if "check divisibility by" in t or "divisible by" in t or "check multiple of" in t:
            m = re.search(r'(\d+)', t)
            div = int(m.group(1)) if m else 5
            return "YES" if int(tokens[0]) % div == 0 else "NO"
        if "check alphabet" in t:
            return "YES" if tokens[0][0].isalpha() else "NO"
        if "vowel" in t and "check" in t:
            return "Vowel" if tokens[0][0].lower() in "aeiou" else "Consonant"

        # Math Series
        if "sum of first n natural numbers" in t or ("natural numbers" in t and "sum" in t and "range" not in t):
            n = int(tokens[0])
            return str(n * (n + 1) // 2)
        if "sum of natural numbers in range" in t:
            a, b = int(tokens[0]), int(tokens[1])
            return str(sum(range(min(a, b), max(a, b) + 1)))
        if "multiplication table" in t:
            n = int(tokens[0])
            return "\n".join(str(n * i) for i in range(1, 11))
        if "print numbers in a range" in t or "print numbers in range" in t:
            a, b = int(tokens[0]), int(tokens[1])
            return " ".join(str(x) for x in range(a, b + 1))
        if "print odd numbers in reverse" in t:
            n = int(tokens[0])
            return " ".join(reversed([str(x) for x in range(1, n + 1) if x % 2 != 0]))
        if "print even numbers in reverse" in t:
            n = int(tokens[0])
            return " ".join(reversed([str(x) for x in range(1, n + 1) if x % 2 == 0]))
        if "print odd numbers" in t:
            n = int(tokens[0])
            return " ".join(str(x) for x in range(1, n + 1, 2))
        if "print numbers in reverse" in t:
            n = int(tokens[0])
            return " ".join(str(x) for x in range(n, 0, -1))
        if "print squares" in t:
            n = int(tokens[0])
            return " ".join(str(i * i) for i in range(1, n + 1))
        if "print factors in descending order" in t:
            n = int(tokens[0])
            return " ".join(str(i) for i in range(n, 0, -1) if n % i == 0)
        if "sum of multiples of" in t:
            m = re.search(r'multiples of (\d+)', t)
            k = int(m.group(1)) if m else 5
            return str(sum(x for x in range(k, int(tokens[0]) + 1, k)))

        # Digits & Numbers
        if "factorial" in t:
            return str(math.factorial(min(20, int(tokens[0]))))
        if "fibonacci" in t:
            n = int(tokens[0])
            if n <= 0: return "0"
            a, b = 0, 1
            for _ in range(n - 1): a, b = b, a + b
            return str(a)
        if "reverse a number" in t or "reverse digits" in t or "reverse number" in t:
            s = tokens[0]
            neg = s.startswith('-')
            rev = s.lstrip('-')[::-1]
            return f"-{int(rev)}" if neg else str(int(rev))
        if "sum of even digits" in t:
            return str(sum(int(d) for d in tokens[0] if d.isdigit() and int(d) % 2 == 0))
        if "sum of odd digits" in t:
            return str(sum(int(d) for d in tokens[0] if d.isdigit() and int(d) % 2 != 0))
        if "sum of digits less than 5" in t:
            return str(sum(int(d) for d in tokens[0] if d.isdigit() and int(d) < 5))
        if "sum of digits at odd positions" in t:
            s = tokens[0]
            return str(sum(int(s[i]) for i in range(0, len(s), 2) if s[i].isdigit()))
        if "sum of digits divisible by 3" in t:
            return str(sum(int(d) for d in tokens[0] if d.isdigit() and int(d) % 3 == 0))
        if "difference of first and last digit" in t:
            digits = [int(d) for d in tokens[0] if d.isdigit()]
            return str(abs(digits[0] - digits[-1]))
        if "sum of first and last digits" in t:
            digits = [int(d) for d in tokens[0] if d.isdigit()]
            return str(digits[0] + digits[-1])
        if "sum of first and last two digits" in t:
            s = tokens[0]
            return str(int(s[:2]) + int(s[-2:]))
        if "sum of digits" in t:
            return str(sum(int(d) for d in tokens[0] if d.isdigit()))
        if "product of digits greater than 3" in t:
            digits = [int(d) for d in tokens[0] if d.isdigit() and int(d) > 3]
            p_val = 1
            for d in digits: p_val *= d
            return str(p_val) if digits else "0"
        if "product of digits" in t:
            digits = [int(d) for d in tokens[0] if d.isdigit()]
            p_val = 1
            for d in digits: p_val *= d
            return str(p_val)
        if "count digits less than 5" in t:
            return str(sum(1 for d in tokens[0] if d.isdigit() and int(d) < 5))
        if "count digits greater than or equal to 5" in t:
            return str(sum(1 for d in tokens[0] if d.isdigit() and int(d) >= 5))
        if "count digit" in t:
            m = re.search(r'count digit (\d)', t)
            target_d = m.group(1) if m else (tokens[1] if len(tokens) > 1 else '5')
            return str(tokens[0].count(target_d))
        if "count digits" in t:
            return str(len(tokens[0].lstrip('-')))
        if "largest digit position" in t:
            digits = [int(d) for d in tokens[0] if d.isdigit()]
            return str(digits.index(max(digits)) + 1)
        if "smallest digit position" in t:
            digits = [int(d) for d in tokens[0] if d.isdigit()]
            return str(digits.index(min(digits)) + 1)
        if "largest and smallest digit" in t:
            digits = [int(d) for d in tokens[0] if d.isdigit()]
            return f"{max(digits)} {min(digits)}"
        if "largest even digit" in t:
            evens = [int(d) for d in tokens[0] if d.isdigit() and int(d) % 2 == 0]
            return str(max(evens)) if evens else "-1"
        if "smallest odd digit" in t:
            odds = [int(d) for d in tokens[0] if d.isdigit() and int(d) % 2 != 0]
            return str(min(odds)) if odds else "-1"
        if "largest digit" in t:
            digits = [int(d) for d in tokens[0] if d.isdigit()]
            return str(max(digits))
        if "smallest digit" in t:
            digits = [int(d) for d in tokens[0] if d.isdigit()]
            return str(min(digits))
        if "find the last digit" in t or "last digit" in t:
            return str(abs(int(tokens[0])) % 10)

        # Arrays
        # Separate Even and Odd
        if "separate even and odd" in t or "move even elements to front" in t or "move evens to front" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            evens = [str(x) for x in nums if x % 2 == 0]
            odds = [str(x) for x in nums if x % 2 != 0]
            return " ".join(evens + odds)
        if "move odd elements to front" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            odds = [str(x) for x in nums if x % 2 != 0]
            evens = [str(x) for x in nums if x % 2 == 0]
            return " ".join(odds + evens)
        if "move negative elements" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            negs = [str(x) for x in nums if x < 0]
            pos = [str(x) for x in nums if x >= 0]
            return " ".join(negs + pos)
        if "move zeros to beginning" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            zeros = [str(x) for x in nums if x == 0]
            nonzeros = [str(x) for x in nums if x != 0]
            return " ".join(zeros + nonzeros)
        if "sum of array elements at odd indices" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            return str(sum(nums[i] for i in range(1, len(nums), 2)))
        if "sum of elements at even indices" in t or "sum of elements at odd positions" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            return str(sum(nums[i] for i in range(0, len(nums), 2)))
        if "sum of even elements" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            return str(sum(x for x in nums if x % 2 == 0))
        if "sum of odd elements" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            return str(sum(x for x in nums if x % 2 != 0))
        if "sum of maximum and minimum" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            return str(max(nums) + min(nums))
        if "difference between maximum and minimum" in t or "minimum and maximum difference" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            return str(max(nums) - min(nums))
        if "minimum element in an array" in t or "minimum element" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            return str(min(nums))
        if "maximum even element" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            evens = [x for x in nums if x % 2 == 0]
            return str(max(evens)) if evens else "-1"
        if "minimum odd element" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            odds = [x for x in nums if x % 2 != 0]
            return str(min(odds)) if odds else "-1"
        if "largest odd element" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            odds = [x for x in nums if x % 2 != 0]
            return str(max(odds)) if odds else "-1"
        if "smallest even element" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            evens = [x for x in nums if x % 2 == 0]
            return str(min(evens)) if evens else "-1"
        if "second largest" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            u = sorted(list(set(nums)))
            return str(u[-2]) if len(u) >= 2 else "-1"
        if "second smallest" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            u = sorted(list(set(nums)))
            return str(u[1]) if len(u) >= 2 else "-1"
        if "largest and second largest" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            u = sorted(list(set(nums)))
            return f"{u[-1]} {u[-2]}" if len(u) >= 2 else f"{u[0]} {u[0]}"
        if "count elements greater than x" in t:
            n = int(tokens[0])
            arr = [int(x) for x in tokens[1:n+1]]
            x = int(tokens[n+1]) if len(tokens) > n+1 else int(tokens[-1])
            return str(sum(1 for val in arr if val > x))
        if "count elements smaller than average" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            avg = sum(nums) / len(nums)
            return str(sum(1 for x in nums if x < avg))
        if "count elements greater than average" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            avg = sum(nums) / len(nums)
            return str(sum(1 for x in nums if x > avg))
        if "count distinct elements" in t or "count unique values" in t or "unique elements" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            return str(len(set(nums)))
        if "find missing value" in t or "missing number" in t:
            n = int(tokens[0])
            nums = [int(x) for x in tokens[1:]]
            return str((n * (n + 1)) // 2 - sum(nums))
        if "find the unique element" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            import collections
            c = collections.Counter(nums)
            for k, v in c.items():
                if v == 1: return str(k)
            return str(nums[0])
        if "find the repeated number" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            seen = set()
            for x in nums:
                if x in seen: return str(x)
                seen.add(x)
            return str(nums[0])
        if "array palindrome" in t:
            nums = tokens[1:] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else tokens
            return "YES" if nums == nums[::-1] else "NO"
        if "array rotation" in t or "rotate array right" in t:
            n = int(tokens[0])
            k = int(tokens[-1]) % n
            arr = tokens[1:n+1]
            return " ".join(arr[-k:] + arr[:-k] if k > 0 else arr)
        if "reverse array in groups" in t:
            n = int(tokens[0])
            k = int(tokens[-1])
            arr = tokens[1:n+1]
            res = []
            for i in range(0, n, k): res.extend(reversed(arr[i:i+k]))
            return " ".join(res)
        if "maximum consecutive ones" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            max_c = cur_c = 0
            for x in nums:
                if x == 1: cur_c += 1; max_c = max(max_c, cur_c)
                else: cur_c = 0
            return str(max_c)
        if "sum of array elements" in t or "sum of elements" in t:
            nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
            return str(sum(nums))

        # Strings
        if "count vowels and consonants" in t:
            s = tokens[0]
            v = sum(1 for ch in s.lower() if ch in "aeiou")
            c = sum(1 for ch in s.lower() if ch.isalpha() and ch not in "aeiou")
            return f"{v} {c}"
        if "count vowels" in t:
            return str(sum(1 for ch in " ".join(tokens).lower() if ch in "aeiou"))
        if "count consonants" in t:
            return str(sum(1 for ch in " ".join(tokens).lower() if ch.isalpha() and ch not in "aeiou"))
        if "count words with even length" in t:
            return str(sum(1 for w in tokens if len(w) % 2 == 0))
        if "count words starting with a vowel" in t:
            return str(sum(1 for w in tokens if w[0].lower() in "aeiou"))
        if "count words ending with a character" in t:
            target = tokens[-1].lower()
            return str(sum(1 for w in tokens[:-1] if w[-1].lower() == target))
        if "count words with a specific character" in t:
            target = tokens[-1].lower()
            return str(sum(1 for w in tokens[:-1] if target in w.lower()))
        if "count character pairs" in t:
            s = tokens[0]
            return str(sum(1 for i in range(len(s) - 1) if s[i] == s[i+1]))
        if "count special characters" in t:
            return str(sum(1 for ch in " ".join(tokens) if not ch.isalnum() and not ch.isspace()))
        if "count alphabetic characters" in t:
            return str(sum(1 for ch in " ".join(tokens) if ch.isalpha()))
        if "count digits in a string" in t:
            return str(sum(1 for ch in " ".join(tokens) if ch.isdigit()))
        if "count uppercase and lowercase" in t:
            s = " ".join(tokens)
            return f"{sum(1 for ch in s if ch.isupper())} {sum(1 for ch in s if ch.islower())}"
        if "count lowercase letters" in t:
            return str(sum(1 for ch in " ".join(tokens) if ch.islower()))
        if "longest word" in t:
            return max(tokens, key=len)
        if "reverse each word" in t:
            return " ".join(w[::-1] for w in tokens)
        if "reverse words with even length" in t:
            return " ".join(w[::-1] if len(w) % 2 == 0 else w for w in tokens)
        if "reverse a string" in t or "reverse string" in t:
            return " ".join(tokens)[::-1]
        if "reverse the string without changing digits" in t:
            s = " ".join(tokens)
            chars = [ch for ch in s if not ch.isdigit()][::-1]
            res, c_idx = [], 0
            for ch in s:
                if ch.isdigit(): res.append(ch)
                else: res.append(chars[c_idx]); c_idx += 1
            return "".join(res)
        if "check anagram" in t or "anagram" in t:
            return "YES" if sorted(tokens[0].lower()) == sorted(tokens[1].lower()) else "NO"
        if "palindrome string" in t or "check palindrome" in t:
            s = "".join(tokens).lower()
            return "YES" if s == s[::-1] else "NO"
        if "string rotation" in t:
            s1, s2 = tokens[0], tokens[1]
            return "YES" if len(s1) == len(s2) and s2 in (s1 + s1) else "NO"
        if "toggle case" in t or "convert case" in t:
            return " ".join(tokens).swapcase()
        if "remove vowels" in t:
            return "".join(ch for ch in " ".join(tokens) if ch.lower() not in "aeiou")
        if "remove a character" in t or "remove a" in t:
            target = tokens[-1]
            s = " ".join(tokens[:-1]) if len(tokens) > 1 else tokens[0]
            return s.replace(target, "")
        if "remove digits" in t:
            return "".join(ch for ch in " ".join(tokens) if not ch.isdigit())
        if "remove special characters" in t:
            return "".join(ch for ch in " ".join(tokens) if ch.isalnum() or ch.isspace())
        if "remove duplicate characters" in t or "remove repeated characters" in t:
            s = tokens[0]
            seen = set()
            res = []
            for ch in s:
                if ch not in seen: seen.add(ch); res.append(ch)
            return "".join(res)
        if "remove consecutive duplicates" in t:
            s = tokens[0]
            res = [s[0]]
            for ch in s[1:]:
                if ch != res[-1]: res.append(ch)
            return "".join(res)
        if "remove consecutive spaces" in t:
            return " ".join(stdin_text.split())
        if "remove duplicate words" in t:
            seen, res = set(), []
            for w in tokens:
                if w not in seen: seen.add(w); res.append(w)
            return " ".join(res)
        if "remove repeated consecutive words" in t:
            res = [tokens[0]]
            for w in tokens[1:]:
                if w != res[-1]: res.append(w)
            return " ".join(res)
        if "most frequent character" in t or "maximum frequency element" in t:
            import collections
            return collections.Counter(tokens[0]).most_common(1)[0][0]
        if "most frequent word" in t:
            import collections
            return collections.Counter(tokens).most_common(1)[0][0]
        if "character replacement" in t:
            return tokens[0].replace(tokens[1], tokens[2])
        if "first vowel" in t:
            for ch in tokens[0]:
                if ch.lower() in "aeiou": return ch
            return "-1"
        if "first character occurrence" in t:
            idx = tokens[0].find(tokens[1])
            return str(idx + 1 if idx != -1 else -1)
        if "first repeated character" in t:
            seen = set()
            for ch in tokens[0]:
                if ch in seen: return ch
                seen.add(ch)
            return "-1"

        # Matrices
        if "matrix total sum" in t:
            r, c = int(tokens[0]), int(tokens[1])
            return str(sum(int(x) for x in tokens[2:2+r*c]))
        if "matrix main diagonal sum" in t or "matrix diagonal sum" in t:
            n = int(tokens[0])
            mat = [[int(tokens[1 + i*n + j]) for j in range(n)] for i in range(n)]
            return str(sum(mat[i][i] for i in range(n)))
        if "sum of main and secondary diagonals" in t:
            n = int(tokens[0])
            mat = [[int(tokens[1 + i*n + j]) for j in range(n)] for i in range(n)]
            s = 0
            for i in range(n):
                s += mat[i][i]
                if i != n - 1 - i: s += mat[i][n - 1 - i]
            return str(s)
        if "matrix secondary diagonal" in t:
            n = int(tokens[0])
            mat = [[int(tokens[1 + i*n + j]) for j in range(n)] for i in range(n)]
            return " ".join(str(mat[i][n - 1 - i]) for i in range(n))
        if "matrix diagonal product" in t:
            n = int(tokens[0])
            mat = [[int(tokens[1 + i*n + j]) for j in range(n)] for i in range(n)]
            p = 1
            for i in range(n): p *= mat[i][i]
            return str(p)
        if "matrix border elements" in t:
            r, c = int(tokens[0]), int(tokens[1])
            mat = [[int(tokens[2 + i*c + j]) for j in range(c)] for i in range(r)]
            border = []
            for i in range(r):
                for j in range(c):
                    if i == 0 or i == r - 1 or j == 0 or j == c - 1:
                        border.append(str(mat[i][j]))
            return " ".join(border)
        if "matrix even element sum" in t:
            r, c = int(tokens[0]), int(tokens[1])
            return str(sum(int(x) for x in tokens[2:2+r*c] if int(x) % 2 == 0))
        if "matrix odd element sum" in t:
            r, c = int(tokens[0]), int(tokens[1])
            return str(sum(int(x) for x in tokens[2:2+r*c] if int(x) % 2 != 0))
        if "row with maximum sum" in t or "matrix maximum row sum" in t:
            r, c = int(tokens[0]), int(tokens[1])
            mat = [[int(tokens[2 + i*c + j]) for j in range(c)] for i in range(r)]
            sums = [sum(row) for row in mat]
            return str(sums.index(max(sums)) + 1)
        if "matrix row with minimum sum" in t or "matrix minimum row sum" in t:
            r, c = int(tokens[0]), int(tokens[1])
            mat = [[int(tokens[2 + i*c + j]) for j in range(c)] for i in range(r)]
            sums = [sum(row) for row in mat]
            return str(sums.index(min(sums)) + 1)
        if "matrix column with maximum sum" in t:
            r, c = int(tokens[0]), int(tokens[1])
            mat = [[int(tokens[2 + i*c + j]) for j in range(c)] for i in range(r)]
            c_sums = [sum(mat[i][j] for i in range(r)) for j in range(c)]
            return str(c_sums.index(max(c_sums)) + 1)
        if "matrix column maximum" in t:
            r, c = int(tokens[0]), int(tokens[1])
            mat = [[int(tokens[2 + i*c + j]) for j in range(c)] for i in range(r)]
            return " ".join(str(max(mat[i][j] for i in range(r))) for j in range(c))
        if "matrix largest element position" in t:
            r, c = int(tokens[0]), int(tokens[1])
            mat = [[int(tokens[2 + i*c + j]) for j in range(c)] for i in range(r)]
            max_v = mat[0][0]
            pos = (1, 1)
            for i in range(r):
                for j in range(c):
                    if mat[i][j] > max_v: max_v = mat[i][j]; pos = (i+1, j+1)
            return f"{pos[0]} {pos[1]}"
        if "matrix minimum element position" in t:
            r, c = int(tokens[0]), int(tokens[1])
            mat = [[int(tokens[2 + i*c + j]) for j in range(c)] for i in range(r)]
            min_v = mat[0][0]
            pos = (1, 1)
            for i in range(r):
                for j in range(c):
                    if mat[i][j] < min_v: min_v = mat[i][j]; pos = (i+1, j+1)
            return f"{pos[0]} {pos[1]}"

        # Search & Sort
        if "linear search" in t:
            if "count occurrences" in t:
                n = int(tokens[0])
                arr = tokens[1:n+1]
                return str(arr.count(tokens[-1]))
            elif "first occurrence of minimum" in t:
                n = int(tokens[0])
                arr = [int(x) for x in tokens[1:n+1]]
                return str(arr.index(min(arr)))
            elif "first negative" in t:
                n = int(tokens[0])
                arr = [int(x) for x in tokens[1:n+1]]
                for idx, v in enumerate(arr):
                    if v < 0: return str(idx)
                return "-1"
            elif "first odd" in t:
                n = int(tokens[0])
                arr = [int(x) for x in tokens[1:n+1]]
                for idx, v in enumerate(arr):
                    if v % 2 != 0: return str(idx)
                return "-1"
            elif "last odd" in t:
                n = int(tokens[0])
                arr = [int(x) for x in tokens[1:n+1]]
                for idx in range(len(arr)-1, -1, -1):
                    if arr[idx] % 2 != 0: return str(idx)
                return "-1"
            elif "target range" in t:
                n = int(tokens[0])
                arr = tokens[1:n+1]
                t_val = tokens[-1]
                indices = [i for i, x in enumerate(arr) if x == t_val]
                return f"{indices[0]} {indices[-1]}" if indices else "-1 -1"
            else:
                n = int(tokens[0])
                arr = tokens[1:n+1]
                return str(arr.index(tokens[-1]) if tokens[-1] in arr else -1)
                
        if "binary search" in t:
            if "greater than or equal" in t or "greater than or equal to x" in t:
                n = int(tokens[0])
                arr = [int(x) for x in tokens[1:n+1]]
                x = int(tokens[-1])
                for idx, val in enumerate(arr):
                    if val >= x: return str(idx)
                return "-1"
            elif "first element greater than x" in t:
                n = int(tokens[0])
                arr = [int(x) for x in tokens[1:n+1]]
                x = int(tokens[-1])
                for idx, val in enumerate(arr):
                    if val > x: return str(idx)
                return "-1"
            elif "first occurrence" in t:
                n = int(tokens[0])
                arr = tokens[1:n+1]
                return str(arr.index(tokens[-1]) if tokens[-1] in arr else -1)
            elif "last occurrence" in t:
                n = int(tokens[0])
                arr = tokens[1:n+1]
                for idx in range(len(arr)-1, -1, -1):
                    if arr[idx] == tokens[-1]: return str(idx)
                return "-1"
            elif "exact or nearest" in t:
                n = int(tokens[0])
                arr = [int(x) for x in tokens[1:n+1]]
                target = int(tokens[-1])
                return str(min(arr, key=lambda val: (abs(val - target), val)))
            else:
                n = int(tokens[0])
                arr = tokens[1:n+1]
                return str(arr.index(tokens[-1]) if tokens[-1] in arr else -1)

        if "bubble sort" in t or "selection sort" in t or "insertion sort" in t:
            if "kth smallest" in t:
                n = int(tokens[0])
                k = int(tokens[-1])
                arr = sorted([int(x) for x in tokens[1:n+1]])
                return str(arr[k - 1])
            elif "kth largest" in t:
                n = int(tokens[0])
                k = int(tokens[-1])
                arr = sorted([int(x) for x in tokens[1:n+1]], reverse=True)
                return str(arr[k - 1])
            elif "descending" in t:
                nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
                return " ".join(str(x) for x in sorted(nums, reverse=True))
            elif "number of swaps" in t:
                n = int(tokens[0])
                arr = [int(x) for x in tokens[1:n+1]]
                swaps = 0
                for i in range(n):
                    min_i = i
                    for j in range(i + 1, n):
                        if arr[j] < arr[min_i]: min_i = j
                    if min_i != i: arr[i], arr[min_i] = arr[min_i], arr[i]; swaps += 1
                return str(swaps)
            else:
                nums = [int(x) for x in tokens[1:]] if len(tokens) > 1 and int(tokens[0]) == len(tokens) - 1 else [int(x) for x in tokens]
                return " ".join(str(x) for x in sorted(nums))

    except Exception as ex:
        pass
        
    return tokens[0] if tokens else ""


def get_inputs(clean_title):
    t = clean_title.lower()
    
    # 1. Two numbers
    if any(k in t for k in ["sum of two numbers", "difference of two", "product of two", "power of a number", "swap two", "largest of two", "smallest of two"]):
        return [
            ("10 20", "10 and 20"),
            ("50 15", "50 and 15")
        ], [
            "0 0",
            "-5 15",
            "100 250",
            "-20 -30",
            "7 3"
        ]

    # 2. Three numbers
    if any(k in t for k in ["average of three", "largest of three", "smallest of three", "middle of three", "maximum of three", "minimum of three"]):
        return [
            ("10 20 30", "10, 20, 30"),
            ("5 15 25", "5, 15, 25")
        ], [
            "3 3 3",
            "0 0 0",
            "100 200 300",
            "-10 0 10",
            "12 24 36"
        ]

    # 3. Matrix
    if "matrix" in t or "diagonal" in t:
        return [
            ("3 3\n1 2 3\n4 5 6\n7 8 9", "3x3 matrix"),
            ("2 2\n10 20\n30 40", "2x2 matrix")
        ], [
            "3 3\n5 5 5\n5 5 5\n5 5 5",
            "2 3\n1 2 3\n4 5 6",
            "3 3\n1 0 0\n0 1 0\n0 0 1",
            "4 4\n1 2 3 4\n5 6 7 8\n9 10 11 12\n13 14 15 16"
        ]

    # 4. Search / Sort with Target / K
    if any(k in t for k in ["linear search", "binary search", "count elements greater than x", "kth smallest", "kth largest", "count occurrences"]):
        return [
            ("5\n10 20 30 40 50\n30", "Array of 5 elements, target 30"),
            ("4\n5 15 25 35\n100", "Array of 4 elements, target 100")
        ], [
            "6\n1 2 3 4 5 6\n1",
            "5\n2 4 6 8 10\n10",
            "7\n-10 -5 0 5 10 15 20\n0",
            "4\n100 200 300 400\n250"
        ]

    # 5. Arrays / Separate Even & Odd / Reversals
    if any(k in t for k in ["array", "element", "sort", "reverse array", "consecutive", "zeroes", "even and odd", "separate", "move"]):
        return [
            ("5\n1 2 3 4 5", "Array [1, 2, 3, 4, 5]"),
            ("4\n10 20 30 40", "Array [10, 20, 30, 40]")
        ], [
            "6\n2 4 6 8 10 12",
            "5\n10 50 20 40 30",
            "5\n1 1 1 1 1",
            "6\n-5 10 -15 20 -25 30"
        ]

    # 6. Strings
    if any(k in t for k in ["string", "word", "character", "vowel", "consonant", "anagram", "palindrome", "case"]):
        if "anagram" in t or "rotation" in t:
            return [
                ("listen silent", "listen and silent"),
                ("hello world", "hello and world")
            ], [
                "triangle integral",
                "apple pale",
                "racecar racecar",
                "abcd bcda"
            ]
        elif "character" in t and ("remove" in t or "count" in t or "replacement" in t):
            return [
                ("programming r", "programming with target r"),
                ("banana a", "banana with target a")
            ], [
                "mississippi s",
                "hello l",
                "world z",
                "spec2026 2"
            ]
        elif "sentence" in t or "word" in t:
            return [
                ("hello world from coding test", "sample sentence 1"),
                ("spec industry hackathon 2026", "sample sentence 2")
            ], [
                "the quick brown fox jumps over the lazy dog",
                "welcome to competitive programming sprint",
                "python cpp java javascript",
                "a bb ccc dddd eeeee"
            ]
        else:
            return [
                ("racecar", "racecar"),
                ("HelloWorld", "HelloWorld")
            ], [
                "madam",
                "programming",
                "12321",
                "SPEC2026"
            ]

    # 7. Single Number / Digits
    return [
        ("12345", "12345"),
        ("10", "10")
    ], [
        "100",
        "7",
        "987654321",
        "0",
        "42"
    ]


def run_bulk_generation():
    db = SessionLocal()
    try:
        print("Starting bulk test case generation for all 350 questions...")
        
        # Clear existing
        db.query(SampleTestCase).delete()
        db.query(HiddenTestCase).delete()
        db.commit()
        
        questions = db.query(Question).order_by(Question.id).all()
        
        samples_to_add = []
        hidden_to_add = []
        
        for q in questions:
            clean_title = re.sub(r'^\[.*?\]\s*', '', q.title).strip()
            sample_inps, hidden_inps = get_inputs(clean_title)
            
            for idx, (inp, note) in enumerate(sample_inps, 1):
                out = solve_fast(clean_title, q.prompt_markdown, inp)
                samples_to_add.append(SampleTestCase(
                    question_id=q.id,
                    input_data=inp,
                    expected_output=out,
                    explanation=f"Input: {inp.replace(chr(10), ' ')} -> Output: {out}",
                    order=idx
                ))
                
            for idx, inp in enumerate(hidden_inps, 1):
                out = solve_fast(clean_title, q.prompt_markdown, inp)
                hidden_to_add.append(HiddenTestCase(
                    question_id=q.id,
                    input_data=inp,
                    expected_output=out,
                    order=idx
                ))
                
        db.bulk_save_objects(samples_to_add)
        db.bulk_save_objects(hidden_to_add)
        db.commit()
        
        print(f"DONE: Inserted {len(samples_to_add)} Sample Cases and {len(hidden_to_add)} Hidden Cases across all {len(questions)} questions.")
        
    finally:
        db.close()

if __name__ == "__main__":
    run_bulk_generation()
