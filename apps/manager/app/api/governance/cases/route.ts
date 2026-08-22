import { NextRequest } from "next/server";
import {
  boundaryErrorResponse,
  caseCreateBody,
  caseListQuery,
  governanceRequest,
  readJsonObject,
  requireIdempotencyKey,
} from "@/app/lib/governance-bff";

export async function GET(request: NextRequest) {
  return governanceRequest(
    `/api/v1/cases/${caseListQuery(request.nextUrl.searchParams)}`,
  );
}

export async function POST(request: NextRequest) {
  try {
    const idempotencyKey = requireIdempotencyKey(request);
    const body = caseCreateBody(await readJsonObject(request));
    return governanceRequest("/api/v1/cases/", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(body),
    });
  } catch (error) {
    return boundaryErrorResponse(error);
  }
}
