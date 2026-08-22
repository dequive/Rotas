import {
  assertUuid,
  boundaryErrorResponse,
  governanceRequest,
  readJsonObject,
  requireIdempotencyKey,
  transitionBody,
} from "@/app/lib/governance-bff";

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await context.params;
    return governanceRequest(`/api/v1/cases/${assertUuid(id)}/transitions`);
  } catch (error) {
    return boundaryErrorResponse(error);
  }
}

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await context.params;
    const caseId = assertUuid(id);
    const idempotencyKey = requireIdempotencyKey(request);
    const body = transitionBody(await readJsonObject(request));
    return governanceRequest(`/api/v1/cases/${caseId}/transitions`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(body),
    });
  } catch (error) {
    return boundaryErrorResponse(error);
  }
}
