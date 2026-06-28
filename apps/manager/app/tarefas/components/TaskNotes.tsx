"use client";

import { User, Send } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";

interface TaskNotesProps {
  taskId: string;
  source: "workshop" | "governance";
}

export function TaskNotes({ taskId, source }: TaskNotesProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!note.trim()) return;

    setLoading(true);
    try {
      if (source === "workshop") {
        // Mocking workshop notes endpoint, assuming it might exist or be added
        await fetch(`/api/v1/workshop/maintenance-requests/${taskId}/notes`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body: note })
        });
      } else {
        await fetch(`/api/v1/governance/cases/${taskId}/notes`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body: note })
        });
      }
      setNote("");
      router.refresh(); // Refresh page data to show new note
    } catch (error) {
      console.error("Error adding note", error);
      alert("Erro ao adicionar nota.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 pt-4 border-t border-slate-100 flex gap-4">
      <div className="w-8 h-8 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center flex-shrink-0">
        <User size={14} />
      </div>
      <div className="flex-1 flex flex-col gap-2">
        <textarea 
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Adicionar um comentário ou nota..."
          className="w-full text-sm px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 min-h-[80px] resize-none"
        />
        <div className="flex justify-end">
          <button 
            type="submit"
            disabled={loading || !note.trim()}
            className="flex items-center gap-2 bg-slate-900 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-slate-800 transition-colors disabled:opacity-50"
          >
            {loading ? "A enviar..." : (
              <>
                Enviar <Send size={14} />
              </>
            )}
          </button>
        </div>
      </div>
    </form>
  );
}
