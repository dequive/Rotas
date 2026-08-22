import { HttpContractError } from "@rotas/http-contract";
import { apiFetch } from "./api";

export interface Employee {
  id: string;
  tenant_id: string;
  first_name: string;
  last_name: string;
  role: string;
  department: string;
  base_salary: number;
  
  employee_number: string | null;
  inss_beneficiary_number: string | null;
  professional_category: string | null;
  irps_tax_percentage: number;
  
  nif_nuit: string | null;
  bank_account_nib: string | null;
  date_of_birth: string | null;
  hire_date: string;
  termination_date: string | null;
  status: "active" | "on_leave" | "terminated";
  driver_id: string | null;
  user_id: string | null;
}

export interface PayrollSlipLine {
  id: string;
  code: string;
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
  irps_tax_percentage: number | null;
  is_taxable_inss: boolean;
  is_taxable_syndicate: boolean;
}

export interface PayrollSlip {
  id: string;
  employee_id: string;
  tenant_id: string;
  period_month: number;
  period_year: number;
  
  gross_salary: number;
  total_inss: number;
  total_irps: number;
  total_syndicate: number;
  total_deductions: number;
  net_salary: number;
  
  status: "draft" | "approved" | "paid";
  payment_date: string | null;
  notes: string | null;
  lines: PayrollSlipLine[];
}

export async function loadEmployees(): Promise<Employee[]> {
  try {
    return await apiFetch<Employee[]>("/api/v1/hr/employees", { revalidate: 0 });
  } catch (err) {
    console.error("Erro ao carregar colaboradores", err);
    return [];
  }
}

export async function createEmployee(payload: Partial<Employee>) {
  return apiFetch("/api/v1/hr/employees", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function generatePayroll(month: number, year: number, employeeId?: string) {
  return apiFetch<PayrollSlip[]>("/api/v1/hr/payroll/generate", {
    method: "POST",
    body: JSON.stringify({
      period_month: month,
      period_year: year,
      employee_id: employeeId || null,
    }),
  });
}

/**
 * Payroll is gated by `hr.salary.view`, which manager and viewer do not hold.
 *
 * A refusal must not come back as an empty list: the page would render
 * "nenhum registo" and tell the user there is no payroll for the month, when
 * in fact there is payroll they are not allowed to see. The caller gets the
 * outcome instead and renders the matching state.
 */
export type PayrollSlipsResult =
  | { status: "ok"; slips: PayrollSlip[] }
  | { status: "forbidden" }
  | { status: "error"; message: string };

export async function loadPayrollSlips(month: number, year: number): Promise<PayrollSlipsResult> {
  try {
    const slips = await apiFetch<PayrollSlip[]>(
      `/api/v1/hr/payroll?month=${month}&year=${year}`,
      { revalidate: 0 },
    );
    return { status: "ok", slips };
  } catch (err) {
    if (err instanceof HttpContractError && err.status === 403) {
      return { status: "forbidden" };
    }
    console.error("Erro ao carregar processamento salarial", err);
    return {
      status: "error",
      message: err instanceof Error ? err.message : "Erro ao carregar o processamento salarial.",
    };
  }
}
