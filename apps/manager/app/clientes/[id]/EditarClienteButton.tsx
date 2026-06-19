"use client";

import { useState } from "react";
import type { ClientResponse } from "@/app/lib/clients-api";
import { ClientFormModal } from "@/app/components/ClientFormModal";

export function EditarClienteButton({ client }: { client: ClientResponse }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        className="secondary-btn"
        onClick={() => setOpen(true)}
      >
        Editar
      </button>
      <ClientFormModal
        mode="edit"
        client={client}
        open={open}
        onOpenChange={setOpen}
      />
    </>
  );
}
