# NovelsProject Crew

Welcome to the NovelsProject Crew project, powered by [crewAI](https://crewai.com). This template is designed to help you set up a multi-agent AI system with ease, leveraging the powerful and flexible framework provided by crewAI. Our goal is to enable your agents to collaborate effectively on complex tasks, maximizing their collective intelligence and capabilities.

## Installation

Ensure you have Python >=3.10 <3.14 installed on your system. This project uses [UV](https://docs.astral.sh/uv/) for dependency management and package handling, offering a seamless setup and execution experience.

First, if you haven't already, install uv:

```bash
pip install uv
```

Next, navigate to your project directory and install the dependencies:

(Optional) Lock the dependencies and install them by using the CLI command:
```bash
crewai install
```
### Customizing

**Add your `OPENAI_API_KEY` into the `.env` file**

- Modify `src/novels_project/config/agents.yaml` to define your agents
- Modify `src/novels_project/config/tasks.yaml` to define your tasks
- Modify `src/novels_project/crew.py` to add your own logic, tools and specific args
- Modify `src/novels_project/main.py` to add custom inputs for your agents and tasks

## Running the Project

### Run with our CLI (`run.py`)

From the root folder of this project:

```bash
python run.py --chapter 1
```

Optional:

```bash
python run.py --chapter 1 --dry-run
```

### Agent model routing

By default, [`NovelsCrewAI`](novels_project/src/novels_project/crew.py:18) uses **two models**:

- Chief Editor + Senior Proofreader: `gemini-3-pro`
- Character Designer + Plot Writer: `glm-5`

Global override:

- If you set `MODEL_NAME` in environment variables, or pass `--model` via your runner (see [`NovelsCrewAI.__init__()`](novels_project/src/novels_project/crew.py:21)), then **all 4 agents will use the same model**.

### Run with CrewAI CLI

To kickstart your crew of AI agents and begin task execution, you can also run:

```bash
$ crewai run
```

This command initializes the novels_project Crew.

## Understanding Your Crew

The novels_project Crew is composed of multiple AI agents, each with unique roles, goals, and tools. These agents collaborate on a series of tasks, defined in `config/tasks.yaml`, leveraging their collective skills to achieve complex objectives. The `config/agents.yaml` file outlines the capabilities and configurations of each agent in your crew.

## Support

For support, questions, or feedback regarding the NovelsProject Crew or crewAI.
- Visit our [documentation](https://docs.crewai.com)
- Reach out to us through our [GitHub repository](https://github.com/joaomdmoura/crewai)
- [Join our Discord](https://discord.com/invite/X4JWnZnxPb)
- [Chat with our docs](https://chatg.pt/DWjSBZn)

Let's create wonders together with the power and simplicity of crewAI.
