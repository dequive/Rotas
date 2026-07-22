"use client";

import { Camera, Check, Loader2, Upload, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";

/**
 * PhotoEvidenceUploader — Upload de fotos de evidência (check-in, peças usadas, etc.)
 *
 * Design rule: o hash SHA-256 é calculado **exclusivamente no servidor** após upload.
 * O cliente NÃO calcula o hash — apenas faz POST multipart/form-data para /api/v1/files/upload.
 * O servidor retorna { id, sha256_hash, url, created_at }.
 */

interface UploadedPhoto {
  id: string;
  url: string;
  sha256_hash: string;
  created_at: string;
}

interface PhotoEvidenceUploaderProps {
  /** Context label shown above the uploader (e.g., "Fotos de Entrada" or "Peça Substituída") */
  label: string;
  /** Maximum number of photos to upload */
  maxPhotos?: number;
  /** Already uploaded photos (e.g., when editing an existing reception) */
  existingPhotos?: UploadedPhoto[];
  /** Called after successful upload with the new photo metadata */
  onUpload?: (photo: UploadedPhoto) => void;
  /** Called when a photo is removed */
  onRemove?: (photoId: string) => void;
  /** Whether the uploader is disabled */
  disabled?: boolean;
}

export function PhotoEvidenceUploader({
  label,
  maxPhotos = 6,
  existingPhotos = [],
  onUpload,
  onRemove,
  disabled = false,
}: PhotoEvidenceUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [photos, setPhotos] = useState<UploadedPhoto[]>(existingPhotos);
  const [error, setError] = useState<string | null>(null);

  const canUpload = photos.length < maxPhotos && !disabled;

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file || !canUpload) return;

      // Validate file type and size
      if (!file.type.startsWith("image/")) {
        setError("Apenas ficheiros de imagem são permitidos.");
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        setError("Ficheiro demasiado grande (máx. 10 MB).");
        return;
      }

      setUploading(true);
      setError(null);

      try {
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch("/api/files/upload", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          const errBody = (await res.json().catch(() => ({}))) as { detail?: string };
          throw new Error(errBody?.detail ?? `Upload falhou: HTTP ${res.status}`);
        }

        const uploaded = (await res.json()) as UploadedPhoto;
        setPhotos((prev) => [...prev, uploaded]);
        onUpload?.(uploaded);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erro no upload.");
      } finally {
        setUploading(false);
        // Reset input so the same file can be re-selected
        if (inputRef.current) inputRef.current.value = "";
      }
    },
    [canUpload, onUpload],
  );

  const handleRemove = useCallback(
    (photoId: string) => {
      setPhotos((prev) => prev.filter((p) => p.id !== photoId));
      onRemove?.(photoId);
    },
    [onRemove],
  );

  return (
    <div className="space-y-3">
      {/* Label */}
      <div className="flex items-center justify-between">
        <label htmlFor="photo-file-input" className="text-sm font-medium text-foreground">{label}</label>
        <span className="text-xs text-muted-foreground">
          {photos.length}/{maxPhotos} fotos
        </span>
      </div>

      {/* Photo grid */}
      <div className="grid grid-cols-3 gap-3">
        {photos.map((photo) => (
          <div
            key={photo.id}
            className="group relative aspect-square rounded-lg border border-border bg-muted/30 overflow-hidden"
          >
            <img
              src={photo.url}
              alt="Evidência fotográfica"
              className="h-full w-full object-cover"
            />
            {/* Hash badge — proves server-side integrity */}
            <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/70 to-transparent px-2 py-1.5">
              <div className="flex items-center gap-1 text-[10px] text-white/80 font-mono truncate">
                <Check className="h-3 w-3 text-emerald-400 flex-shrink-0" />
                {photo.sha256_hash.slice(0, 12)}…
              </div>
            </div>
            {/* Remove button */}
            {!disabled && (
              <button
                onClick={() => handleRemove(photo.id)}
                className="absolute top-1.5 right-1.5 rounded-full bg-black/60 p-1 text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/80"
                title="Remover foto"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        ))}

        {/* Upload trigger */}
        {canUpload && (
          <button
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="relative flex flex-col items-center justify-center gap-2 aspect-square rounded-lg border-2 border-dashed border-border bg-muted/20 hover:bg-muted/40 hover:border-primary/40 transition-all text-muted-foreground hover:text-foreground cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uploading ? (
              <>
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
                <span className="text-[11px] font-medium">A enviar…</span>
              </>
            ) : (
              <>
                <Camera className="h-6 w-6" />
                <span className="text-[11px] font-medium">Adicionar Foto</span>
              </>
            )}
          </button>
        )}
      </div>

      {/* Hidden file input */}
      <input
        ref={inputRef}
        id="photo-file-input"
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* Error message */}
      {error && (
        <p className="text-xs text-rose-500 flex items-center gap-1.5">
          <Upload className="h-3.5 w-3.5" />
          {error}
        </p>
      )}
    </div>
  );
}
