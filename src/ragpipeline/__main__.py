import argparse

from ragpipeline.index import create_index, reset_index
from ragpipeline.ingest import ingest


def cmd_ingest(args):
    if getattr(args, "recreate", False):
        reset_index()
    else:
        create_index()
    if getattr(args, "data_dir", None):
        count = ingest(data_dir=args.data_dir)
    else:
        count = ingest()
    print(f"ingested {count} chunks")


def cmd_reset(args):
    name = reset_index()
    print(f"reset index: {name}")


def cmd_ask(args):
    from ragpipeline.pipeline import answer

    result = answer(args.question, mode=args.mode)
    print(result["answer"])
    print(f"\nmode: {result['mode']}")
    print("sources:")
    for doc in result["sources"]:
        print(f"  - {doc['id']} (score={doc.get('score')})")


def main():
    parser = argparse.ArgumentParser(prog="ragpipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_parser = sub.add_parser("ingest")
    ingest_parser.add_argument("--recreate", action="store_true")
    ingest_parser.add_argument("--data-dir", default=None)
    ingest_parser.set_defaults(func=cmd_ingest)
    sub.add_parser("reset").set_defaults(func=cmd_reset)

    ask = sub.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--mode", default="hybrid")
    ask.set_defaults(func=cmd_ask)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
