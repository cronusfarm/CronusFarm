import json


IDA_FLOWS_IN = ".tmp_flows_ida.json"
IDA_FLOWS_OUT = ".tmp_flows_ida_patched.json"


def main() -> None:
    a = json.load(open(IDA_FLOWS_IN, "r", encoding="utf-8"))

    for n in a:
        if not isinstance(n, dict):
            continue

        if n.get("id") == "http_kma_get":
            # KMA 응답이 JSON이 아닐 때(오류/XML) 노드가 바로 죽지 않게 텍스트로 받습니다.
            n["ret"] = "txt"

        if n.get("id") == "fn_kma_to_influx":
            code = n.get("func", "")
            guard = """

// http request 노드가 텍스트로 들어올 수 있어, 문자열이면 JSON 파싱을 시도합니다.
if (typeof msg.payload === "string") {
  const raw = msg.payload;
  try {
    msg.payload = JSON.parse(raw);
  } catch (e) {
    node.warn("KMA: JSON 파싱 실패(응답 일부): " + raw.slice(0, 200));
    return null;
  }
}
"""
            if 'typeof msg.payload === "string"' not in code:
                marker = "if (!token) return null;"
                if marker in code:
                    code = code.replace(marker, marker + guard)
                else:
                    code = guard + code
                n["func"] = code

    json.dump(a, open(IDA_FLOWS_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("patched ok:", IDA_FLOWS_OUT)


if __name__ == "__main__":
    main()

