"""Sample keynote transcripts for Catch up. Recordings are not public yet, so these are generated and labelled.

uv run python -m app.data.transcripts --generate   # one-off: ask Claude for 3 transcripts, write the JSON file
uv run python -m app.data.transcripts --load       # split into ~200-word chunks and rebuild confox-transcripts

--generate costs real money and is run once; the result is committed in data/sample/transcripts.json so loading
never calls Claude. Each transcript is written from the keynote's public title and description only.
"""

import argparse
import json
import logging

from elasticsearch.helpers import bulk
from opentelemetry import trace

from .. import clock
from ..config import ROOT, settings
from ..es import es

log = logging.getLogger("confox.transcripts")
tracer = trace.get_tracer("confox.transcripts")

TRANSCRIPTS_FILE = ROOT / "data" / "sample" / "transcripts.json"
# Three Tuesday 10 November keynotes with real descriptions in the public schedule, close to Emma's interests.
KEYNOTE_IDS = ["1301696", "1349401", "1301749"]
CHUNK_WORDS = 200

GENERATE_SYSTEM = (
    "You write plausible sample transcripts of conference keynotes for a demo app. The app labels them as "
    "generated samples. Work only from the title, speakers and description you are given: do not invent "
    "product launches, numbers, customer names or quotes from real people beyond what the description says. "
    "Write about 1200 words of spoken prose as the speakers would say it, in paragraphs separated by blank "
    "lines. When there are several speakers, prefix a paragraph with the speaker's name and a colon when the "
    "speaker changes. No headings, no stage directions, no markdown."
)


def chunk(text: str, size: int = CHUNK_WORDS) -> list[str]:
    """Split on paragraphs into chunks of about `size` words; a long paragraph is split on words."""
    chunks: list[str] = []
    current: list[str] = []
    count = 0
    for para in (p.strip() for p in text.split("\n\n")):
        if not para:
            continue
        words = para.split()
        while len(words) > size * 1.5:  # an unusually long paragraph: cut it rather than make one huge chunk
            head, words = words[:size], words[size:]
            if current:
                chunks.append("\n\n".join(current))
                current, count = [], 0
            chunks.append(" ".join(head))
        if count and count + len(words) > size:
            chunks.append("\n\n".join(current))
            current, count = [], 0
        current.append(" ".join(words))
        count += len(words)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def chunk_docs(transcripts: list[dict]) -> list[dict]:
    docs = []
    for t in transcripts:
        for n, text in enumerate(chunk(t["text"]), start=1):
            docs.append(
                {
                    "id": f"{t['session_id']}-{n}",
                    "doc_type": "chunk",
                    "session_id": t["session_id"],
                    "chunk": n,
                    "text": text,
                    "sample": True,
                }
            )
    return docs


def generate() -> None:
    from .. import llm  # only the generator needs Claude

    docs = es.mget(index=settings.idx_sessions, ids=KEYNOTE_IDS)["docs"]
    out = []
    for d in docs:
        s = d["_source"]
        prompt = (
            f"Title: {s['title']}\nSpeakers: {', '.join(s.get('speaker_names') or []) or 'unknown'}\n"
            f"Event: KubeCon + CloudNativeCon North America 2026, Salt Lake City, keynote on Tuesday 10 November\n"
            f"Description: {s.get('description') or ''}\n\nWrite the sample transcript."
        )
        text, usage = llm.complete(
            GENERATE_SYSTEM,
            [{"role": "user", "content": prompt}],
            feature="transcript-generate",
            max_tokens=6000,
            effort="low",
        )
        log.info("%s: %d words, %s", d["_id"], len(text.split()), usage.as_dict())
        out.append({"session_id": d["_id"], "title": s["title"], "sample": True, "model": usage.model, "text": text})

    TRANSCRIPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sample": True,
        "note": "Generated sample transcripts, written by Claude from each keynote's public title and description. "
        "Not real recordings.",
        "generated_at": clock.now().isoformat(),
        "transcripts": out,
    }
    TRANSCRIPTS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    log.info("wrote %s", TRANSCRIPTS_FILE)


def load() -> int:
    from ..indices import rebuild

    transcripts = json.loads(TRANSCRIPTS_FILE.read_text())["transcripts"]
    docs = chunk_docs(transcripts)
    index = settings.idx_transcripts
    with tracer.start_as_current_span(f"load {index}") as span:
        rebuild(index)
        ok, _ = bulk(
            es, ({"_index": index, "_id": d["id"], "_source": {k: v for k, v in d.items() if k != "id"}} for d in docs)
        )
        es.indices.refresh(index=index)
        span.set_attribute("confox.docs", ok)
        log.info("%s: %d chunks from %d transcripts", index, ok, len(transcripts))
        return ok


def main() -> None:
    from ..telemetry import setup_telemetry, shutdown_telemetry

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--generate", action="store_true", help="call Claude and rewrite the JSON file")
    parser.add_argument("--load", action="store_true", help="index the JSON file into Elasticsearch")
    args = parser.parse_args()
    if not (args.generate or args.load):
        parser.error("choose --generate, --load or both")

    setup_telemetry(service_name="confox-load")
    try:
        if args.generate:
            generate()
        if args.load:
            load()
    finally:
        shutdown_telemetry()


if __name__ == "__main__":
    main()
