import * as React from 'react';
import { FileSpreadsheet, UploadCloud } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table';
import { DetailRow } from '@/components/ui/feedback';
import { num } from '@/lib/format';
import { useLegacyImport } from './catalogue-api';

/** Every exception is an arbitrary `{...}` object — rendered as its own key/value pairs. */
type ExceptionRow = Record<string, unknown>;

export function LegacyImportPanel() {
  const legacyImport = useLegacyImport();
  const fileRef = React.useRef<HTMLInputElement>(null);
  const [file, setFile] = React.useState<File | null>(null);

  const result = legacyImport.data;
  const exceptions: ExceptionRow[] = result?.exceptions ?? [];

  async function submit() {
    if (!file) return;
    await legacyImport.mutateAsync(file);
    setFile(null);
    if (fileRef.current) fileRef.current.value = '';
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3 rounded-xl border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">
          A folha é validada, não é considerada de confiança — cada linha problemática fica
          reportada como exceção em vez de ser corrigida em silêncio.
        </p>
        <p className="text-sm text-muted-foreground">
          Repetir a importação da mesma folha não duplica nada: faturas e produtos já criados são
          reconhecidos e reutilizados.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx"
            className="hidden"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <Button type="button" variant="outline" onClick={() => fileRef.current?.click()}>
            <FileSpreadsheet />
            Escolher ficheiro
          </Button>
          {file ? <span className="text-sm text-muted-foreground">{file.name}</span> : null}
          <Button disabled={!file} loading={legacyImport.isPending} onClick={submit}>
            <UploadCloud />
            Importar
          </Button>
        </div>
      </div>

      {result ? (
        <div className="space-y-4">
          <dl className="grid gap-x-6 rounded-xl border border-border bg-card p-4 sm:grid-cols-2">
            <DetailRow label="Linhas lidas">{num(result.row_count)}</DetailRow>
            <DetailRow label="Faturas criadas">{num(result.receipts_created)}</DetailRow>
            <DetailRow label="Faturas reconciliadas">{num(result.receipts_reconciled)}</DetailRow>
            <DetailRow label="Faturas por validar">{num(result.receipts_needing_review)}</DetailRow>
            <DetailRow label="Linhas Fs">{num(result.fs_rows)}</DetailRow>
            <DetailRow label="Linhas Fs reencaixadas">{num(result.fs_rows_snapped)}</DetailRow>
            <DetailRow label="Grupos só-Fs">{num(result.all_fs_groups)}</DetailRow>
            <DetailRow label="Produtos criados">{num(result.products_created)}</DetailRow>
            <DetailRow label="Aliases criados">{num(result.aliases_created)}</DetailRow>
            <DetailRow label="Comerciantes criados">{num(result.merchants_created)}</DetailRow>
            <DetailRow label="Linhas não-alimentares ignoradas">
              {num(result.skipped_non_grocery_rows)}
              {result.skipped_non_grocery_merchants.length
                ? ` (${result.skipped_non_grocery_merchants.join(', ')})`
                : ''}
            </DetailRow>
          </dl>

          <div className="space-y-2 rounded-lg border border-dashed border-border p-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold">Exceções</p>
              <p className="text-xs text-muted-foreground">Reportadas, não corrigidas em silêncio.</p>
            </div>
            {exceptions.length ? (
              <Table>
                <TableBody>
                  {exceptions.map((exception, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        <dl className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs">
                          {Object.entries(exception).map(([key, value]) => (
                            <React.Fragment key={key}>
                              <dt className="text-muted-foreground">{key}</dt>
                              <dd className="truncate">
                                {typeof value === 'string' || typeof value === 'number'
                                  ? String(value)
                                  : JSON.stringify(value)}
                              </dd>
                            </React.Fragment>
                          ))}
                        </dl>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">Sem exceções nesta importação.</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
