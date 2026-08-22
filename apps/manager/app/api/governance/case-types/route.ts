import { governanceRequest } from "@/app/lib/governance-bff";

export async function GET() {
  return governanceRequest("/api/v1/cases/types/");
}
