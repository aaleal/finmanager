import {
  Ban,
  CheckCircle2,
  CircleDot,
  Clock,
  Loader2,
  RotateCcw,
  ScanLine,
  XCircle,
} from 'lucide-react';
import type { ReceiptStatus } from '@/lib/types';

export type BadgeTone = 'default' | 'secondary' | 'outline' | 'success' | 'warning' | 'destructive' | 'muted';

interface StatusMeta {
  label: string;
  variant: BadgeTone;
  icon: typeof CheckCircle2;
}

/** Every receipt status, always paired with an icon so colour is never the only signal. */
export const RECEIPT_STATUS_META: Record<ReceiptStatus, StatusMeta> = {
  UPLOADED: { label: 'Carregada', variant: 'muted', icon: Clock },
  PARSING: { label: 'A processar', variant: 'secondary', icon: Loader2 },
  AUTO_ACCEPTED: { label: 'Aceite automaticamente', variant: 'success', icon: CheckCircle2 },
  NEEDS_REVIEW: { label: 'Por validar', variant: 'warning', icon: ScanLine },
  CONFIRMED: { label: 'Confirmada', variant: 'success', icon: CheckCircle2 },
  VOID: { label: 'Anulada', variant: 'destructive', icon: Ban },
  FAILED: { label: 'Falhada', variant: 'destructive', icon: XCircle },
};

export const RECEIPT_STATUS_OPTIONS: { value: ReceiptStatus; label: string }[] = (
  Object.keys(RECEIPT_STATUS_META) as ReceiptStatus[]
).map((value) => ({ value, label: RECEIPT_STATUS_META[value].label }));

interface JobStatusMeta {
  label: string;
  variant: BadgeTone;
  icon: typeof CheckCircle2;
}

export const JOB_STATUS_META: Record<string, JobStatusMeta> = {
  QUEUED: { label: 'Em fila', variant: 'muted', icon: Clock },
  RUNNING: { label: 'Em execução', variant: 'secondary', icon: Loader2 },
  SUCCEEDED: { label: 'Concluído', variant: 'success', icon: CheckCircle2 },
  FAILED: { label: 'Falhou', variant: 'destructive', icon: XCircle },
  RETRYING: { label: 'A repetir', variant: 'warning', icon: RotateCcw },
};

export const FS_FILTER_OPTIONS = [
  { value: 'all', label: 'Todos' },
  { value: 'only', label: 'Só Fs' },
  { value: 'exclude', label: 'Sem Fs' },
] as const;

export const UNIT_OPTIONS = [
  { value: 'UN', label: 'Unidade (un)' },
  { value: 'KG', label: 'Quilograma (kg)' },
  { value: 'G', label: 'Grama (g)' },
  { value: 'L', label: 'Litro (l)' },
  { value: 'ML', label: 'Mililitro (ml)' },
  { value: 'PACK', label: 'Embalagem (pack)' },
] as const;

export const DEFAULT_ICON = CircleDot;
