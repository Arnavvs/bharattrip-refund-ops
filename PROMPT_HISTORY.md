# Prompt history

Actual task prompts provided by the user in this session, in order:

1. "there's some data and project details start working on it and explain me the working of our solution"
2. "i guess they are expecting some kinf od dashboard or pipeline? theres render and vercel open on chrome - host the solution. make a github repo too"

The project brief PDF and supplied workbook were the task's source context. They were read directly. Code, analysis and documentation were produced in the same ChatGPT/Codex conversation. No external LLM API was called by the prototype. This file is the actual user-prompt history available to this build, not a reconstruction of separate AI sessions or a full ChatGPT export.

## Decisions made with AI assistance

- Select reconciliation and exception handling as the useful operational slice.
- Preserve source data, normalise references and dates, remove exact repeats and quarantine ambiguous repeats.
- Separate complaint wording from verified payment evidence.
- Build an offline text-retrieval triage baseline and label it honestly.
- Keep payment, eligibility and customer communication under human control.
- Host the Python dashboard on Render with source and checks in GitHub.

## Revision request (actual user prompt)

> okay check the work done previously cross check, make a better dashboard it takes a lot of time in certain tasks like choosing priority and reloading the table, - inspect case etc
> in general make the dashboard better check the pdf with project details and excel
> for final pdf keep it in under 2 pages- concise to show clear thinking instead of length
> also for prompt history just make a very good 2-3 prompts in line for this project as if i sent them to codex and show me final pdf,project i can submit and get selected for sure.

## Three prompts to reproduce the approach

1. Read the brief and all four workbook tabs. Reconcile Support and Finance by normalized refund ID, separate duplicate rows from conflicting IDs, and tell me which handoff failures the evidence supports. Show the denominators.
2. Build an operations queue where selecting a priority or inspecting a case never reopens Excel. Show the source evidence and next action. Use complaint text for routing suggestions and require human review for payments and ambiguous matches.
3. Test the queue on both the workbook and generated demo data. Give me a one-page decision memo with the diagnosis, ownership change, two measurable targets and links to the working prototype.
