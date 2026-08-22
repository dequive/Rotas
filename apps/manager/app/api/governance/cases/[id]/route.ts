import {
  assertUuid,
  boundaryErrorResponse,
  governanceRequest,
} from "@/app/lib/governance-bff";

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await context.params;
    return governanceRequest(`/api/v1/cases/${assertUuid(id)}`);
  } catch (error) {
    return boundaryErrorResponse(error);
  }
}
