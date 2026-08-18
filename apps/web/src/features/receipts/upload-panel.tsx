import * as React from 'react';
import { Camera, FileText, UploadCloud, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Field } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { useParserProfiles, useUploadReceipts } from './api';
import { ReceiptQueueTable } from './queue-table';

const ACCEPT = 'application/pdf,image/*';
/** Detection picks the profile unless the household overrides it. */
const AUTO_PROFILE = '__auto__';

export function ReceiptUploadPanel({ onUploaded }: { onUploaded?: () => void }) {
  const upload = useUploadReceipts();
  const profiles = useParserProfiles();
  const [files, setFiles] = React.useState<File[]>([]);
  const [profileId, setProfileId] = React.useState(AUTO_PROFILE);
  const [dragging, setDragging] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);
  const cameraRef = React.useRef<HTMLInputElement>(null);

  function addFiles(list: FileList | null) {
    if (!list) return;
    setFiles((previous) => [...previous, ...Array.from(list)]);
  }

  function removeFile(index: number) {
    setFiles((previous) => previous.filter((_, i) => i !== index));
  }

  async function submit() {
    if (!files.length) return;
    await upload.mutateAsync({
      files,
      parserProfileId: profileId === AUTO_PROFILE ? undefined : profileId,
    });
    setFiles([]);
    onUploaded?.();
  }

  return (
    <div className="space-y-4">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          addFiles(event.dataTransfer.files);
        }}
        className={cn(
          'flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-border bg-card/50 px-6 py-12 text-center transition-colors',
          dragging && 'border-primary bg-primary/5',
        )}
      >
        <div className="flex size-11 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <UploadCloud className="size-5" />
        </div>
        <div className="space-y-1">
          <p className="font-medium">Arraste as faturas para aqui</p>
          <p className="mx-auto max-w-sm text-sm text-muted-foreground">
            Pode largar várias faturas de uma vez — cada uma é processada de forma independente.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button type="button" variant="outline" onClick={() => fileRef.current?.click()}>
            <FileText />
            Escolher ficheiros
          </Button>
          <Button type="button" variant="outline" onClick={() => cameraRef.current?.click()}>
            <Camera />
            Tirar fotografia
          </Button>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept={ACCEPT}
          multiple
          className="hidden"
          onChange={(event) => {
            addFiles(event.target.files);
            event.target.value = '';
          }}
        />
        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(event) => {
            addFiles(event.target.files);
            event.target.value = '';
          }}
        />
      </div>

      <Field
        label="Perfil de leitura"
        hint="Por omissão o comerciante é detetado no documento e escolhe o perfil. Force um perfil quando a deteção falhar — fica gravado na fatura."
      >
        <Select value={profileId} onValueChange={setProfileId}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={AUTO_PROFILE}>Detetar automaticamente</SelectItem>
            {(profiles.data ?? [])
              .filter((profile) => profile.is_active)
              .map((profile) => (
                <SelectItem key={profile.id} value={profile.id}>
                  {profile.name}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
      </Field>

      {files.length ? (
        <div className="space-y-2 rounded-xl border border-border bg-card p-4">
          <ul className="space-y-1.5">
            {files.map((file, index) => (
              <li
                key={`${file.name}-${index}`}
                className="flex items-center justify-between gap-2 text-sm"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <FileText className="size-4 shrink-0 text-muted-foreground" />
                  <span className="truncate">{file.name}</span>
                </span>
                <button
                  type="button"
                  onClick={() => removeFile(index)}
                  aria-label={`Remover ${file.name}`}
                  className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted"
                >
                  <X className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
          <Button loading={upload.isPending} disabled={upload.isPending} onClick={submit}>
            <UploadCloud />
            Carregar
          </Button>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Carregar is an action, not a place (ADR-0026): the drop zone and the live
 * processing queue live in a modal opened from the invoice list, so uploading
 * never costs the household its position in the list it was looking at.
 */
export function ReceiptUploadDialog() {
  const [open, setOpen] = React.useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <UploadCloud />
          Carregar faturas
        </Button>
      </DialogTrigger>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UploadCloud className="size-4" />
            Carregar faturas
          </DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-6">
          <ReceiptUploadPanel />
          <div className="space-y-2">
            <p className="text-sm font-semibold">Em processamento</p>
            <ReceiptQueueTable compact />
          </div>
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}
