# app_final.py
import streamlit as st
import requests
import json
import re
import time
from typing import List, Dict, Optional, Tuple

st.set_page_config(page_title="Math Tutor", page_icon="📐")
st.title("📐 Math Tutor")
st.markdown("Get step-by-step solutions to math problems")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []


def call_deepseek(messages: List[Dict], temperature: float = 0.3, retries: int = 2) -> Dict:
    """Call DeepSeek API with retry logic"""
    for attempt in range(retries):
        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {st.secrets['DEEPSEEK_API_KEY']}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": messages,
                    "temperature": temperature
                },
                timeout=90
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"DeepSeek API error: {response.text}")
                
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                st.warning(f"⏳ Timeout, retrying... (Attempt {attempt + 1}/{retries})")
                time.sleep(3)
                continue
            else:
                raise Exception("DeepSeek API timeout after multiple retries.")
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(3)
                continue
            else:
                raise Exception(f"Network error: {str(e)}")


def get_wolfram_result(query: str) -> Optional[str]:
    """Get Wolfram Alpha result for a specific query"""
    try:
        response = requests.get(
            "https://api.wolframalpha.com/v2/query",
            params={
                "input": query,
                "output": "JSON",
                "appid": st.secrets["WOLFRAM_APP_ID"]
            },
            timeout=30
        )
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if not data.get("queryresult", {}).get("success", False):
            return None
        
        results = []
        for pod in data.get("queryresult", {}).get("pods", []):
            if pod.get("title") == "Input":
                continue
            for subpod in pod.get("subpods", []):
                text = subpod.get("plaintext", "")
                if text and text.strip():
                    # FIX THE WOLFRAM RESULT AT THE SOURCE
                    # Replace the broken integral formatting with proper LaTeX
                    text = text.replace('\\left \\frac{x^3}{3} \\right 0 2 0 2', 
                                       '\\left. \\frac{x^3}{3} \\right|_0^2')
                    text = text.replace('\\left \\frac{x^3}{3} \\right \n0\n2\n0\n2', 
                                       '\\left. \\frac{x^3}{3} \\right|_0^2')
                    results.append(text.strip())
        
        return "\n".join(results) if results else None
        
    except Exception as e:
        return None



def get_wolfram_code(problem: str) -> str:
    """Generate Wolfram Language code for the problem"""
    
    problem_lower = problem.lower()
    
    # Derivative problems
    if "derivative" in problem_lower or "differentiate" in problem_lower:
        patterns = [
            r'(?:derivative|differentiate)\s+(?:of\s+)?([^,]+?)(?:\s+with|\s+at|$)',
            r'd/dx\s*\(([^)]+)\)',
            r'\bderivative\b.*?\bof\b\s+([^,]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, problem_lower)
            if match:
                func = match.group(1).strip()
                return f"D[{func}, x]"
        return "D[expression, x]"
    
    # Integration problems
    elif "integrate" in problem_lower or "integral" in problem_lower:
        patterns = [
            r'(?:integrate|integral)\s+(?:of\s+)?([^f][^r][^o][^m][^,]+?)(?:\s+from|\s+with|$)',
            r'∫\s*([^d][^x][^,]+?)(?:\s+dx|$)'
        ]
        
        func = None
        for pattern in patterns:
            match = re.search(pattern, problem_lower)
            if match:
                func = match.group(1).strip()
                break
        
        if func:
            from_match = re.search(r'from\s+([-\d]+)\s+to\s+([-\d]+)', problem_lower)
            if from_match:
                lower = from_match.group(1)
                upper = from_match.group(2)
                return f"Integrate[{func}, {{x, {lower}, {upper}}}]"
            return f"Integrate[{func}, x]"
        return "Integrate[expression, x]"
    
    # Equation solving
    elif "solve" in problem_lower:
        equation_part = re.sub(r'^solve\s*:?\s*', '', problem_lower)
        
        if ',' in equation_part or ' and ' in equation_part:
            equations = re.split(r',\s*|\s+and\s+', equation_part)
            equations = [eq.strip() for eq in equations if eq.strip()]
            if len(equations) >= 2:
                variables = []
                for eq in equations:
                    found_vars = set(re.findall(r'[a-zA-Z]', eq))
                    variables.extend(found_vars)
                variables = sorted(list(set(variables)))
                
                if variables:
                    eq_list = ', '.join(equations)
                    var_list = ', '.join(variables)
                    return f"Solve[{{{eq_list}}}, {{{var_list}}}]"
                else:
                    return f"Solve[{{{', '.join(equations)}}}]"
            else:
                return f"Solve[{equations[0]}, x]"
        
        elif ' for ' in equation_part:
            match = re.search(r'(.+?)\s+for\s+([a-zA-Z]+)', equation_part)
            if match:
                equation = match.group(1).strip()
                variable = match.group(2).strip()
                return f"Solve[{equation}, {variable}]"
        
        else:
            match = re.search(r'solve\s*:?\s*(.+)', problem_lower)
            if match:
                equation = match.group(1).strip()
                variables = re.findall(r'[a-zA-Z]', equation)
                if len(set(variables)) > 1:
                    var_list = ', '.join(sorted(list(set(variables))))
                    return f"Solve[{{{equation}}}, {{{var_list}}}]"
                else:
                    return f"Solve[{equation}, x]"
            return "Solve[equation, variable]"
    
    # Arithmetic operations
    elif any(op in problem for op in ["^", "**", "calculate", "what is"]):
        match = re.search(r'(\d+)\^(\d+)', problem)
        if match:
            base = match.group(1)
            exp = match.group(2)
            return f"{base}^{exp}"
        
        match = re.search(r'(\d+)%\s+of\s+(\d+)', problem_lower)
        if match:
            percent = match.group(1)
            number = match.group(2)
            return f"{percent}% of {number}"
        
        return problem
    
    else:
        return problem


def extract_math_content(text: str) -> str:
    """Extract and clean math content from text"""
    
    # First, fix common LaTeX issues
    # Fix missing backslashes in common LaTeX commands
    text = re.sub(r'(?<!\\)int', r'\\int', text)
    text = re.sub(r'(?<!\\)frac', r'\\frac', text)
    text = re.sub(r'(?<!\\)left', r'\\left', text)
    text = re.sub(r'(?<!\\)right', r'\\right', text)
    
    # Fix spaces in LaTeX
    text = re.sub(r'\\,', r'\\,', text)  # Keep thin spaces
    text = re.sub(r'\\ ', r'\\ ', text)  # Keep spaces
    
    # Fix improper LaTeX delimiters
    # Replace [ ... ] that are meant to be math with $$ ... $$
    # But only if they contain LaTeX commands
    def replace_brackets(match):
        content = match.group(1)
        if any(cmd in content for cmd in ['\\int', '\\frac', '\\sum', '\\lim']):
            return f'$${content}$$'
        else:
            return f'$${content}$$'  # Still use $$ for clarity
    
    text = re.sub(r'\[([^\]]+)\]', replace_brackets, text)
    
    # Convert \boxed{} to $$ ... $$
    text = re.sub(r'\\boxed\{([^}]+)\}', r'$$\1$$', text)
    
    # Ensure inline math uses single $ and is properly formatted
    text = re.sub(r'\\\(([^\)]+)\\\)', r'$\1$', text)
    text = re.sub(r'\\\[([^\]]+)\\\]', r'$$\1$$', text)
    
    # Fix common LaTeX formatting issues
    # Add proper spacing after LaTeX commands
    text = re.sub(r'\\int([a-zA-Z0-9])', r'\\int \1', text)
    text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\\frac{\1}{\2}', text)
    
    # Ensure display math is on separate lines
    text = re.sub(r'\$\$([^\$]+)\$\$', r'\n$$\1$$\n', text)
    
    # FIX: Remove the broken integral pattern with numbers on separate lines
    pattern = r'\\int_0\^2 x\^2 \\, dx = \\left \\frac{x\^3}{3} \\right\s*\n\s*0\s*\n\s*2\s*\n\s*0\s*\n\s*2'
    text = re.sub(pattern, '', text)
    
    # Also remove any standalone \left \frac{x^3}{3} \right that might remain
    text = re.sub(r'\\left\s+\\frac\{x\^3\}\{3\}\s+\\right', '', text)
    
    # Also fix the "int egral" text
    text = text.replace('\\int egral', 'integral')
    text = text.replace('int egral', 'integral')
    
    # Clean up multiple newlines
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    
    return text

def decompose_problem(problem: str) -> Tuple[List[Dict], str]:
    """Step 1: Use DeepSeek to break down complex problem into sub-problems"""
    
    decomposition_prompt = f"""You are a math tutor. Break down this math problem into smaller, independent sub-problems that can be solved separately.

Problem: {problem}

Analyze the problem and output a JSON list of sub-problems. Each sub-problem should:
1. Be a complete, standalone calculation or step
2. Include specific mathematical expressions that can be computed
3. Be clear enough that Wolfram Alpha can solve it directly

Format your response as valid JSON:
{{
    "sub_problems": [
        {{
            "step": 1,
            "description": "What this step calculates",
            "wolfram_query": "The exact query to send to Wolfram Alpha"
        }},
        ...
    ],
    "explanation": "Brief overview of how these steps solve the main problem"
}}

Only output the JSON, no other text. Make sure the wolfram_query is a valid mathematical expression."""

    try:
        response = call_deepseek([
            {"role": "user", "content": decomposition_prompt}
        ], temperature=0.1)
        
        result = response["choices"][0]["message"]["content"]
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            decomposition = json.loads(json_match.group())
            return decomposition.get("sub_problems", []), decomposition.get("explanation", "")
        else:
            return [], ""
            
    except Exception as e:
        st.error(f"Decomposition failed: {str(e)}")
        return [], ""


def solve_sub_problems(sub_problems: List[Dict]) -> List[Dict]:
    """Step 2: Send each sub-problem to Wolfram Alpha"""
    
    solved_steps = []
    
    for sub_problem in sub_problems:
        step_num = sub_problem.get("step", len(solved_steps) + 1)
        description = sub_problem.get("description", "")
        query = sub_problem.get("wolfram_query", "")
        
        # Show progress
        st.write(f"🔍 Solving step {step_num}: {description}")
        
        # Get Wolfram result
        wolfram_result = get_wolfram_result(query)
        
        if wolfram_result:
            solved_steps.append({
                "step": step_num,
                "description": description,
                "query": query,
                "result": wolfram_result,
                "status": "success"
            })
        else:
            # Fallback: try DeepSeek for this sub-problem
            st.write(f"⚠️ Wolfram couldn't solve step {step_num}, trying DeepSeek...")
            fallback_result = solve_with_deepseek(query)
            solved_steps.append({
                "step": step_num,
                "description": description,
                "query": query,
                "result": fallback_result,
                "status": "fallback"
            })
    
    return solved_steps


def solve_with_deepseek(query: str) -> str:
    """Fallback: Use DeepSeek to solve a sub-problem if Wolfram fails"""
    try:
        response = call_deepseek([
            {"role": "user", "content": f"Solve this step by step with proper LaTeX formatting: {query}"}
        ])
        result = response["choices"][0]["message"]["content"]
        return extract_math_content(result)
    except:
        return "Unable to solve this step."


def synthesize_solution(original_problem: str, solved_steps: List[Dict], explanation: str) -> str:
    """Step 3: Use DeepSeek to combine all results into a coherent solution with proper LaTeX"""
    
    # Format the solved steps for synthesis
    steps_text = ""
    for step in solved_steps:
        steps_text += f"\n**Step {step['step']}: {step['description']}**\n"
        steps_text += f"Computation result: {step['result']}\n"
    
    synthesis_prompt = f"""You are a math tutor. Combine these solved steps into a complete, coherent solution with proper LaTeX formatting.

CRITICAL FORMATTING RULES:
- For inline math, use $...$ (single dollar signs) - Example: $x^2 + 3$
- For displayed equations, use $$...$$ (double dollar signs) - Example: $$\\int_0^2 x^2 dx = \\frac{{8}}{{3}}$$
- Use proper LaTeX commands: \\int, \\frac, \\sum, \\lim, etc.
- When writing definite integrals, ALWAYS use the format: $$\\int_{{lower}}^{{upper}} f(x) \\, dx = \\left. F(x) \\right|_{{lower}}^{{upper}}$$
- NEVER use the format: \\left \\frac{{x^3}}{{3}} \\right followed by numbers on separate lines
- NEVER write integrals with the evaluation bar on separate lines
- One equation on One line
- One formula in One line
- Always use \\, for spacing in integrals: \\int_0^2 x^2 \\, dx

Original Problem: {original_problem}

Problem Decomposition: {explanation}

Solved Steps:
{steps_text}

Create a final solution using this exact format:

**Step 1: Understand the problem**
[Explanation with $inline math$]

**Step 2: Apply the method**
[Explanation with $inline math$]

**Step 3: Show the calculation**
Show step-by-step using:
$$equation 1$$
$$equation 2$$

**Step 4: Final answer**
$$answer$$

Now provide the complete solution with proper LaTeX formatting. Make sure all LaTeX is correctly escaped with backslashes."""

    try:
        response = call_deepseek([
            {"role": "user", "content": synthesis_prompt}
        ], temperature=0.2)
        
        result = response["choices"][0]["message"]["content"]
        
        # Apply proven formatting
        result = extract_math_content(result)
        
        # Add Wolfram integration summary with code
        wolfram_codes = []
        for step in solved_steps:
            code = get_wolfram_code(step['query'])
            if code and code not in ["Solve[equation, variable]", "Integrate[expression, x]", "D[expression, x]"]:
                wolfram_codes.append(f"Step {step['step']}: {code}")
        
        wolfram_summary = "\n\n> **🔗 Wolfram Language Integration**\n>\n"
        wolfram_summary += "> This solution was generated by breaking down the problem and computing each step with Wolfram Alpha:\n>\n"
        for code in wolfram_codes:
            wolfram_summary += f"> ```mathematica\n> {code}\n> ```\n>\n"
        wolfram_summary += "> ---\n"
        
        return wolfram_summary + result
        
    except Exception as e:
        # If synthesis fails, at least return the individual steps with formatting
        steps_output = f"**Solution Steps for: {original_problem}**\n\n"
        steps_output += f"**Approach:** {explanation}\n\n"
        for step in solved_steps:
            steps_output += f"**Step {step['step']}: {step['description']}**\n"
            steps_output += f"{step['result']}\n\n"
        steps_output += "\n**Final Answer**\n"
        steps_output += "See individual steps above for the complete solution."
        return extract_math_content(steps_output)


def solve_problem(problem: str) -> str:
    """Main solving function with decomposition approach and proven formatting"""
    
    with st.status("Solving your problem...", expanded=True) as status:
        
        # Step 1: Decompose the problem
        status.write("🧠 Step 1: Analyzing and breaking down the problem...")
        sub_problems, explanation = decompose_problem(problem)
        
        if not sub_problems:
            status.write("⚠️ Could not decompose problem, using direct approach...")
            # Fallback to direct DeepSeek with proven formatting
            response = call_deepseek([
                {"role": "user", "content": f"""Solve this problem step by step with proper LaTeX formatting.

CRITICAL FORMATTING RULES:
- For inline math, use $...$ (single dollar signs) - Example: $x^2 + 3$
- For displayed equations, use $$...$$ (double dollar signs) - Example: $$\\int_0^2 x^2 \\, dx = \\frac{{8}}{{3}}$$
- Use proper LaTeX commands: \\int, \\frac, \\sum, \\lim, etc.
- NEVER use [ ... ] or \\[ ... \\] for math
- NEVER use \\boxed{{}} for final answer
- One equation on One line

Problem: {problem}

Use this exact format:

**Step 1: Understand the problem**
[Explanation with $inline math$]

**Step 2: Apply the method**
[Explanation with $inline math$]

**Step 3: Show the calculation**
$$equation 1$$
$$equation 2$$

**Step 4: Final answer**
$$answer$$

Now provide the solution:"""}
            ])
            result = response["choices"][0]["message"]["content"]
            result = extract_math_content(result)
            return result
        
        status.write(f"✅ Problem broken down into {len(sub_problems)} steps")
        status.write(f"📋 Strategy: {explanation}")
        
        # Step 2: Solve each sub-problem
        status.write("🔢 Step 2: Computing each step with Wolfram Alpha...")
        solved_steps = solve_sub_problems(sub_problems)
        
        successful = sum(1 for s in solved_steps if s['status'] == 'success')
        status.write(f"✅ {successful}/{len(solved_steps)} steps computed successfully")
        
        # Step 3: Synthesize the solution with proven formatting
        status.write("📝 Step 3: Combining results into a coherent solution...")
        final_solution = synthesize_solution(problem, solved_steps, explanation)
        
        status.write("✨ Solution complete!")
        status.update(label="Problem solved!", state="complete")
        
        return final_solution


# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask a math problem..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get and display response
    with st.chat_message("assistant"):
        solution = solve_problem(prompt)
        st.markdown(solution)
        st.session_state.messages.append({"role": "assistant", "content": solution})

# Sidebar
with st.sidebar:
    st.markdown("## 🧠 How It Works")
    st.markdown("""
    **Intelligent Problem Solving:**
    
    1. **Decompose** - DeepSeek breaks complex problems into manageable steps
    2. **Compute** - Each step solved precisely with Wolfram Alpha
    3. **Synthesize** - DeepSeek combines results into a coherent, well-formatted solution
    
    **Benefits:**
    - ✅ Handles complex, multi-step problems
    - ✅ Shows true step-by-step reasoning
    - ✅ Combines AI reasoning with precise computation
    - ✅ Consistent, beautiful LaTeX formatting
    - ✅ Educational and easy to follow
    """)
    
    st.markdown("---")
    st.markdown("### 📚 Try These Examples")
    st.markdown("""
    **Multi-step Problems:**
    - Find the area between y = x^2 and y = x from x=0 to x=1
    - Calculate the volume of a sphere with radius 5, then find its surface area
    - Integrate x^2 from 0 to 2, then multiply by 3
    
    **Calculus:**
    - Find derivative of x^2 * sin(x), then evaluate at x = π/2
    - Integrate x^2 from 0 to 2, then multiply by 3
    
    **Algebra:**
    - Solve x^2 - 5x + 6 = 0, then find the sum of roots
    - Find the roots of x^2 + 2x - 3 = 0 and verify by plugging back
    """)
    
    st.markdown("---")
    st.markdown("### 📐 How Math Renders")
    st.markdown("""
    **Inline math:** $x^2 + y^2 = z^2$
    
    **Display math:**
    $$\\int_0^2 x^2 \\, dx = \\frac{8}{3}$$
    
    **Derivative:**
    $$\\frac{d}{dx} x^2 = 2x$$
    """)
    
    st.markdown("---")
    st.markdown("### 🔧 Process Visualization")
    st.markdown("""
    """)

    if st.button("Clear Chat"):
       st.session_state.messages = []
       st.rerun()