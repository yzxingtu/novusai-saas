import http from "k6/http";
import { check } from "k6";

export default function () {
  const baseUrl = (__ENV.API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
  const targetPath = __ENV.CAPACITY_TARGET_PATH || "/ready";
  const response = http.get(`${baseUrl}${targetPath}`, {
    tags: { endpoint: "ready" },
  });

  check(response, {
    "ready status is 200": (res) => res.status === 200,
    "ready payload is true": (res) => {
      try {
        const payload = res.json();
        return payload && payload.data && payload.data.ready === true;
      } catch (_error) {
        return false;
      }
    },
  });
}
