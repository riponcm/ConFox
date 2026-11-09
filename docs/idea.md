# Idea

## Problem

A large conference is a scheduling and people problem. At KubeCon North America:

- **Too many sessions.** Hundreds of talks run in parallel rooms; the official schedule lists them all with equal weight.
- **The wrong people.** The people you would learn most from are somewhere in the crowd, and you have no way to find them.
- **Missed talks are gone.** A clash, a long queue, a caregiving call, a mobility limit or a hearing need means a talk is simply lost.

## Persona

**Emma**, a platform engineer and University of Utah alumna attending her first KubeCon. She cares about AI inference on Kubernetes and GPU scheduling. It is Monday 8:40 AM; co-located events start at 9:00. She wants to know where to be, who to meet, and how to catch up on the keynote she will miss.

## Features

Priority: **Must** (the demo needs it) · **Should** (strong for a track) · **Could** (only if time).

| Feature | Priority | User story |
|---|---|---|
| Search | Must | As Emma, I describe what I want ("running LLM inference cheaply on GPUs") and get the right talks first, even when the words differ. |
| Schedule · For you | Must | As Emma, I see my day with only the sessions that fit my profile, plus keynotes and breaks; I can switch to everything. |
| People · Match | Must | As Emma, I see people ranked by shared interests and background, with the reason ("University of Utah alumni"); clicking a reason filters by it. |
| Ask | Must | As Emma, I ask a question and get an answer that cites real sessions. |
| Catch up | Must | As Emma, I read a summary and takeaways of a talk I missed and ask questions about it. |
| Dashboard | Should | As Emma, I see the conference at a glance: sessions over the day, what fills up next, tracks. |
| Now | Should | As Emma, I see what is on now, next, and the next coffee or food. |
| Connect | Should | As Emma, I request a short meeting and get a slot that is free for both of us. |
| Agenda | Should | As Emma, I save sessions and get warned about real clashes. |
| My brief | Could | As Emma, I get one page for my day. |

## Principles

- **Elasticsearch is the only store.** Sessions, people, agendas and transcripts all live there.
- **Observable from the first hour.** Every request is traced; LLM calls record tokens and cost.
- **Simple first.** Each feature ships in its simplest useful form, then improves.
- **Honest data.** Attendee profiles and talk transcripts in the demo are generated samples and labelled as such.

## Out of scope

- Real attendee accounts and sign-in (the demo user is signed in by default).
- Real talk recordings (generated sample transcripts stand in, labelled).
- Kubernetes deployment (the app runs with Docker Compose).
