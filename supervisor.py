from langchain_groq import ChatGroq
from groq import Groq
import os

os.environ["GROQ_API_KEY"] = "YOUR_API_HERE"  #inserT yor api key here

llm = ChatGroq(
    model_name="llama3-70b-8192",    # select model here
    temperature=0.2,
    max_tokens=2048,
)

agents = {
    "literature": {
        "role": "Literature Researcher",
        "goal": "Find relevant papers on a given topic.",
        "backstory": "Expert at scientific search."
    },
    "summarizer": {
        "role": "Summarizer",
        "goal": "Summarize findings from papers.",
        "backstory": "Excellent at synthesizing insights."
    },
    "hypothesis": {
        "role": "Hypothesis Generator",
        "goal": "Propose new research hypotheses.",
        "backstory": "Creative scientific thinker."
    },
    "reviewer": {
        "role": "Peer Reviewer",
        "goal": "Review hypotheses for novelty and scientific merit.",
        "backstory": "Experienced, skeptical scientist."
    },
    "supervisor": {
        "role": "Supervisor",
        "goal": "Review each step's result. If not up to the mark, ask the responsible agent to redo their work, else approve and pass to next step.",
        "backstory": "Leads the research project, ensuring high standards and efficient workflow. Always critical, provides actionable feedback."
    },
}


def agent_act(agent, task_description):
    prompt = (
        f"Role: {agent['role']}\n"
        f"Goal: {agent['goal']}\n"
        f"Backstory: {agent['backstory']}\n"
        f"Task: {task_description}\n"
        f"Instructions: Respond as {agent['role']}, keeping in character.\n"
    )
    response = llm.invoke(prompt)
    print(f"\n--- {agent['role']} Output ---\n{response}\n")
    return response


def supervised_workflow():
    topic = "machine learning for protein folding"

    print("\n=== LITERATURE RESEARCH ===")
    research_task = f"List 3-5 recent, relevant papers on: '{topic}'. For each, include a 2-sentence summary."
    research_output = agent_act(agents["literature"], research_task)

    print("\n=== SUPERVISOR REVIEWS RESEARCH ===")
    sup_research_task = (
        "Review the following research output for completeness and relevance. "
        "If it is incomplete, missing important recent work, or unclear, write a message to the Researcher asking for revision. "
        "If it is excellent, say ONLY 'Approved' at the end.\n\nResearch Output:\n"
        + str(research_output)
    )

    max_retries = 3
    retries = 0
    while retries < max_retries:
        sup_feedback = agent_act(agents["supervisor"], sup_research_task)
        if "Approved" in sup_feedback:
            break
        print(f"Supervisor requested revision. Attempt {retries+1} of {max_retries}.")

        revised_task = (
            f"The supervisor gave you this feedback: '{sup_feedback}'. "
            f"Please revise your previous output accordingly.\n"
            f"Here was your previous output:\n{research_output}"
        )
        research_output = agent_act(agents["literature"], revised_task)

        sup_research_task = (
            "Review the following revised research output. "
            "If excellent, say ONLY 'Approved' at the end.\n\nResearch Output:\n"
            + str(research_output)
        )
        retries += 1

    if "Approved" in sup_feedback:
        print("Maximum retries reached. Halting workflow.")
        return


    print("\n=== SUMMARIZATION ===")
    summary_task = "Summarize the main findings and key insights from these papers:\n" + str(research_output)
    summary_output = agent_act(agents["summarizer"], summary_task)

    print("\n=== SUPERVISOR REVIEWS SUMMARY ===")
    sup_summary_task = (
        "Review the following summary for clarity, accuracy, and completeness. "
        "If it is incomplete, unclear, or misses important points, write a message to the Summarizer asking for revision. "
        "If it is excellent, say ONLY 'Approved' at the end.\n\nSummary Output:\n"
        + str(summary_output)
    )
    sup_feedback = agent_act(agents["supervisor"], sup_summary_task)
    if "Approved" not in sup_feedback:
        print("Supervisor requested revision. (Expand with retry logic here if desired.)")
        return

    print("\n=== HYPOTHESIS GENERATION ===")
    hypo_task = "Based on this summary, propose two new research hypotheses. Each hypothesis should have a short explanation:\n" + summary_output
    hypo_output = agent_act(agents["hypothesis"], hypo_task)

    print("\n=== SUPERVISOR REVIEWS HYPOTHESES ===")
    sup_hypo_task = (
        "Review the following hypotheses for novelty, scientific merit, and clarity. "
        "If they are weak or unclear, write a message to the Hypothesis Generator asking for revision. "
        "If they are both strong, say ONLY 'Approved' at the end.\n\nHypotheses Output:\n"
        + str(hypo_output)
    )
    sup_feedback = agent_act(agents["supervisor"], sup_hypo_task)
    if "Approved" not in sup_feedback:
        print("Supervisor requested revision. (Expand with retry logic here if desired.)")
        return

    print("\n=== PEER REVIEW ===")
    review_task = "Review these hypotheses for scientific value, potential weaknesses, and suggest improvements:\n" + str(hypo_output)
    review_output = agent_act(agents["reviewer"], review_task)

    print("\n=== SUPERVISOR FINAL REVIEW ===")
    sup_final_task = (
        "Give a final project evaluation based on the research, summary, hypotheses, and peer review below. "
        "Highlight strengths and any remaining issues. End your evaluation with the word 'COMPLETE'.\n\n"
        f"Research: {research_output}\n\n"
        f"Summary: {summary_output}\n\n"
        f"Hypotheses: {hypo_output}\n\n"
        f"Peer Review: {review_output}"
    )
    agent_act(agents["supervisor"], sup_final_task)
    print("\n=== ALL DONE! ===")

if __name__ == "__main__":
    supervised_workflow()
