"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { ClientFormModal } from "@/app/components/ClientFormModal";

export function NovoClienteButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button className="primary-btn" onClick={() => setOpen(true)}>
        <Plus size={15} style={{ display: "inline", marginRight: 6 }} />
        Novo Cliente
      </button>
      <ClientFormModal
        mode="create"
        open={open}
        onOpenChange={setOpen}
      />
    </>
  );
}
