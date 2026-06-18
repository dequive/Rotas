"use client";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-4">
      <p className="text-[14px] text-error font-semibold">Erro ao carregar dados: {error.message}</p>
      <button
        onClick={reset}
        className="inline-flex items-center h-9 px-4 text-[13px] font-semibold border border-border rounded-md hover:bg-surface-2 transition-colors duration-75"
      >
        Tentar novamente
      </button>
    </div>
  );
}
