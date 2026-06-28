"use client";

import { useState } from "react";
import { User } from "lucide-react";
import { DriverHubDrawer } from "./DriverHubDrawer";

export function DriverHubButton({
  driverId,
  driverName,
}: {
  driverId: string;
  driverName: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button 
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 text-blue-600 hover:text-blue-800 font-medium transition-colors"
      >
        <User size={14} />
        {driverName}
      </button>

      {open && (
        <DriverHubDrawer
          driverId={driverId}
          open={open}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
