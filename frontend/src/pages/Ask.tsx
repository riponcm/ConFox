import { DEMO_USER } from '../api.ts'
import ChatThread from '../components/ask/ChatThread.tsx'
import '../styles/ask.css'

const STARTERS = [
  'Which talks today are about running LLM inference cheaply on GPUs?',
  'Where should I go this week to learn about GPU scheduling with Kubeflow or KServe?',
  'Who should I meet about eBPF and GPU scheduling?',
  'What did the Tuesday keynotes say about running AI agents safely?',
]

export default function Ask() {
  return (
    <section className="page ask-page" aria-labelledby="page-title">
      <h1 id="page-title">Ask Confox</h1>
      <p className="page-lead">
        Ask about the schedule or who to meet. Answers come from the sessions and people Confox finds, with numbered sources you can check.
      </p>
      <ChatThread
        endpoint="ask"
        extraBody={{ user_id: DEMO_USER }}
        label="Ask Confox conversation"
        placeholder="Ask about talks, people, rooms or times"
        starters={STARTERS}
      />
    </section>
  )
}
