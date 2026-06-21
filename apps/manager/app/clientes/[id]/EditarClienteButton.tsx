"use client";

import { useState } from "react";
import type { ClientResponse } from "@/app/lib/clients-api";
import { ClientFormModal } from "@/app/components/ClientFormModal";
import { Button } from "@/app/components/ui/Button";

export function EditarClienteButton({ client }: { client: ClientResponse }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Editar
      </Button>
      <ClientFormModal
        mode="edit"
        client={client}
        open={open}
        onOpenChange={setOpen}
      />
    </>
  );
}
