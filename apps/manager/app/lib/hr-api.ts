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

export async function loadPayrollSlips(month: number, year: number): Promise<PayrollSlip[]> {
  try {
    return await apiFetch<PayrollSlip[]>(`/api/v1/hr/payroll?month=${month}&year=${year}`, { revalidate: 0 });
  } catch (err) {
    console.error("Erro ao carregar processamento salarial", err);
    return [];
  }
}
