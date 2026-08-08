"use client";

import { bffFetch } from "./bff";
import type { Employee, PayrollSlip } from "./hr-api";

export function createEmployee(payload: Partial<Employee>) {
  return bffFetch("/api/v1/hr/employees", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function generatePayroll(month: number, year: number, employeeId?: string) {
  return bffFetch<PayrollSlip[]>("/api/v1/hr/payroll/generate", {
    method: "POST",
    body: JSON.stringify({
      period_month: month,
      period_year: year,
      employee_id: employeeId || null,
    }),
  });
}
