"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { ClientFormModal } from "@/app/components/ClientFormModal";
import { Button } from "@/app/components/ui/Button";

export function NovoClienteButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="primary" onClick={() => setOpen(true)}>
        <Plus size={15} />
        Novo Cliente
      </Button>
      <ClientFormModal
        mode="create"
        open={open}
        onOpenChange={setOpen}
      />
    </>
  );
}
