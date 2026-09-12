import * as React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { DatabaseBackup, KeyRound, ShieldAlert, Trash2, Upload } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { useSession } from '@/features/auth/session';
import type { AppSettings } from '@/lib/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Field, Input, PasswordInput } from '@/components/ui/input';
import { Separator, Switch } from '@/components/ui/primitives';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { PageHeader } from '@/components/ui/feedback';
import { useBackupModules, useExportBackup, useImportBackup } from '@/features/settings/backup-api';
import { usePurgeCollection, usePurgeStorageLocations } from '@/features/lego/api';
import { usePurgeCategories, usePurgeProducts } from '@/features/supermarket/catalogue-api';

const KEYS = {
  bricksetEnabled: 'lego.brickset.enabled',
  bricksetKey: 'lego.brickset.api_key',
  staleDays: 'lego.stale_value_days',
  autoAccept: 'confidence.auto_accept',
  review: 'confidence.review',
};

function PasswordCard() {
  const { logout } = useSession();
  const [current, setCurrent] = React.useState('');
  const [next, setNext] = React.useState('');

  const change = useMutation({
    mutationFn: () => api.post('/auth/password', { current_password: current, new_password: next }),
    onSuccess: async () => {
      toast.success('Palavra-passe alterada. Inicie sessão novamente.');
      await logout();
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : 'Erro.'),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-4 text-muted-foreground" />
          Palavra-passe
        </CardTitle>
        <CardDescription>
          Alterar a palavra-passe termina todas as sessões abertas, incluindo esta.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Field label="Palavra-passe atual">
          <PasswordInput
            autoComplete="current-password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
          />
        </Field>
        <Field label="Nova palavra-passe" hint="Mínimo 8 caracteres.">
          <PasswordInput
            autoComplete="new-password"
            value={next}
            onChange={(event) => setNext(event.target.value)}
          />
        </Field>
        <Button
          onClick={() => change.mutate()}
          disabled={!current || next.length < 8}
          loading={change.isPending}
        >
          Alterar
        </Button>
      </CardContent>
    </Card>
  );
}

function BackupCard() {
  const { canWrite } = useSession();
  const modules = useBackupModules();
  const [scope, setScope] = React.useState('all');
  const exportBackup = useExportBackup();
  const importBackup = useImportBackup();
  const restoreInput = React.useRef<HTMLInputElement>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <DatabaseBackup className="size-4 text-muted-foreground" />
          Cópia de segurança
        </CardTitle>
        <CardDescription>
          Arquivo com identificadores, imagens e histórico de valores — repõe um módulo, ou toda a
          instalação, numa instalação vazia. As chaves primárias viajam; a entidade de cada registo
          é resolvida pelo nome e os documentos são remapeados; linhas já existentes são mantidas,
          nunca substituídas. Importe primeiro o módulo «Entidades» para que os outros módulos
          encontrem as entidades certas pelo nome.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Field label="Âmbito">
          <Select value={scope} onValueChange={setScope}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tudo</SelectItem>
              {(modules.data ?? []).map((module) => (
                <SelectItem key={module.key} value={module.key}>
                  {module.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            loading={exportBackup.isPending}
            onClick={() => exportBackup.mutate(scope)}
          >
            <DatabaseBackup />
            Criar cópia
          </Button>
          {canWrite ? (
            <>
              <input
                ref={restoreInput}
                type="file"
                accept=".zip,application/zip"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) importBackup.mutate(file);
                  event.target.value = '';
                }}
              />
              <Button
                variant="outline"
                title="O ficheiro decide sozinho se repõe um módulo ou a instalação inteira."
                loading={importBackup.isPending}
                onClick={() => restoreInput.current?.click()}
              >
                <Upload />
                Repor a partir de arquivo
              </Button>
            </>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function LegoDangerZoneCard() {
  const [confirmCollection, setConfirmCollection] = React.useState(false);
  const [confirmStorage, setConfirmStorage] = React.useState(false);
  const purgeCollection = usePurgeCollection();
  const purgeStorage = usePurgeStorageLocations();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Trash2 className="size-4 text-muted-foreground" />
          LEGO — limpar para reimportar
        </CardTitle>
        <CardDescription>
          Elimina definitivamente conjuntos, cópias ou locais de arrumação, sem passar por
          <code className="mx-1 rounded bg-muted px-1 py-0.5 text-xs">./fm reset</code>
          nem pelo resto da instalação. Use antes de uma reimportação limpa.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Button variant="destructive" onClick={() => setConfirmCollection(true)}>
          <Trash2 />
          Eliminar toda a coleção
        </Button>
        <Button variant="destructive" onClick={() => setConfirmStorage(true)}>
          <Trash2 />
          Eliminar locais de arrumação
        </Button>
      </CardContent>

      <Dialog open={confirmCollection} onOpenChange={setConfirmCollection}>
        <DialogContent size="sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Trash2 className="size-4" />
              Eliminar toda a coleção
            </DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3 text-sm text-muted-foreground">
            <p>
              Isto elimina <strong className="text-foreground">definitivamente</strong> todos os
              conjuntos e cópias registados — galeria de imagens e manuais incluídos. Não afeta os
              locais de arrumação. Não pode ser desfeito.
            </p>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmCollection(false)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              loading={purgeCollection.isPending}
              onClick={async () => {
                await purgeCollection.mutateAsync();
                setConfirmCollection(false);
              }}
            >
              Eliminar definitivamente
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmStorage} onOpenChange={setConfirmStorage}>
        <DialogContent size="sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Trash2 className="size-4" />
              Eliminar locais de arrumação
            </DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3 text-sm text-muted-foreground">
            <p>
              Isto elimina <strong className="text-foreground">definitivamente</strong> todos os
              locais de arrumação. As cópias que lá estavam guardadas ficam sem local atribuído, mas
              não são eliminadas. Não pode ser desfeito.
            </p>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmStorage(false)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              loading={purgeStorage.isPending}
              onClick={async () => {
                await purgeStorage.mutateAsync();
                setConfirmStorage(false);
              }}
            >
              Eliminar definitivamente
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function SupermarketDangerZoneCard() {
  const [confirmProducts, setConfirmProducts] = React.useState(false);
  const [confirmCategories, setConfirmCategories] = React.useState(false);
  const purgeProducts = usePurgeProducts();
  const purgeCategories = usePurgeCategories();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Trash2 className="size-4 text-muted-foreground" />
          Supermercado — limpar para reimportar
        </CardTitle>
        <CardDescription>
          Elimina definitivamente todos os produtos ou toda a árvore de categorias, sem passar por
          <code className="mx-1 rounded bg-muted px-1 py-0.5 text-xs">./fm reset</code>
          nem pelo resto da instalação. Use antes de uma reimportação limpa.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Button variant="destructive" onClick={() => setConfirmProducts(true)}>
          <Trash2 />
          Eliminar todos os produtos
        </Button>
        <Button variant="destructive" onClick={() => setConfirmCategories(true)}>
          <Trash2 />
          Eliminar todas as categorias
        </Button>
      </CardContent>

      <Dialog open={confirmProducts} onOpenChange={setConfirmProducts}>
        <DialogContent size="sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Trash2 className="size-4" />
              Eliminar todos os produtos
            </DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3 text-sm text-muted-foreground">
            <p>
              Isto elimina <strong className="text-foreground">definitivamente</strong> todo o
              catálogo de produtos, mesmo os já referenciados por recibos — as linhas de recibo
              ficam sem produto associado, mas os próprios recibos não são afetados. Não pode ser
              desfeito.
            </p>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmProducts(false)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              loading={purgeProducts.isPending}
              onClick={async () => {
                await purgeProducts.mutateAsync();
                setConfirmProducts(false);
              }}
            >
              Eliminar definitivamente
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmCategories} onOpenChange={setConfirmCategories}>
        <DialogContent size="sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Trash2 className="size-4" />
              Eliminar todas as categorias
            </DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3 text-sm text-muted-foreground">
            <p>
              Isto elimina <strong className="text-foreground">definitivamente</strong> toda a
              árvore de categorias, mesmo as ainda em uso — os produtos afetados ficam sem
              categoria, nunca eliminados. Não pode ser desfeito.
            </p>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmCategories(false)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              loading={purgeCategories.isPending}
              onClick={async () => {
                await purgeCategories.mutateAsync();
                setConfirmCategories(false);
              }}
            >
              Eliminar definitivamente
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export function SettingsPage() {
  const { isOwner } = useSession();
  const queryClient = useQueryClient();

  const settings = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get<AppSettings>('/settings'),
  });

  const [apiKey, setApiKey] = React.useState('');

  const update = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      api.patch<AppSettings>('/settings', { values }),
    onSuccess: (result) => {
      queryClient.setQueryData(['settings'], result);
      toast.success('Definições guardadas.');
      setApiKey('');
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : 'Erro.'),
  });

  const values = settings.data?.values ?? {};
  const bricksetEnabled = Boolean(values[KEYS.bricksetEnabled]);
  const hasApiKey = Boolean(values[KEYS.bricksetKey]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Definições"
        description="Fornecedores externos, limiares de confiança e a sua conta."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Brickset</CardTitle>
            <CardDescription>
              Único fornecedor de metadados de conjuntos LEGO. Desativado por omissão e contactado
              apenas quando carrega em «procurar» — nunca automaticamente.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between gap-4 rounded-lg border border-border p-3">
              <div>
                <p className="text-sm font-medium">Consulta ao Brickset</p>
                <p className="text-xs text-muted-foreground">
                  {hasApiKey ? 'Chave da API configurada.' : 'Falta configurar a chave da API.'}
                </p>
              </div>
              <Switch
                checked={bricksetEnabled}
                disabled={!isOwner}
                onCheckedChange={(checked) => update.mutate({ [KEYS.bricksetEnabled]: checked })}
              />
            </div>

            {isOwner ? (
              <div className="space-y-2">
                <Field
                  label="Chave da API"
                  hint="Gratuita em brickset.com/tools/webservices/v3. Nunca é devolvida ao navegador depois de guardada."
                >
                  <Input
                    type="password"
                    value={apiKey}
                    placeholder={hasApiKey ? '••••••••••••' : 'key-XXXX-XXXX-XXXX'}
                    onChange={(event) => setApiKey(event.target.value)}
                  />
                </Field>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!apiKey}
                  loading={update.isPending}
                  onClick={() => update.mutate({ [KEYS.bricksetKey]: apiKey })}
                >
                  Guardar chave
                </Button>
              </div>
            ) : null}

            <Separator />

            <Field
              label="Valor considerado desatualizado após"
              hint="Dias desde a última atualização manual do valor de mercado."
            >
              <Input
                type="number"
                min={7}
                max={3650}
                defaultValue={String(values[KEYS.staleDays] ?? 180)}
                disabled={!isOwner}
                onBlur={(event) =>
                  update.mutate({ [KEYS.staleDays]: Number(event.target.value) || 180 })
                }
              />
            </Field>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldAlert className="size-4 text-muted-foreground" />
                Limiares de confiança
              </CardTitle>
              <CardDescription>
                Usados pelos módulos de ingestão: acima do primeiro valor a decisão é aceite
                automaticamente; abaixo do segundo é descartada.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <Field label="Aceitação automática">
                <Input
                  type="number"
                  step="0.05"
                  min={0}
                  max={1}
                  defaultValue={String(values[KEYS.autoAccept] ?? 0.9)}
                  disabled={!isOwner}
                  onBlur={(event) =>
                    update.mutate({ [KEYS.autoAccept]: Number(event.target.value) })
                  }
                />
              </Field>
              <Field label="Enviar para revisão">
                <Input
                  type="number"
                  step="0.05"
                  min={0}
                  max={1}
                  defaultValue={String(values[KEYS.review] ?? 0.6)}
                  disabled={!isOwner}
                  onBlur={(event) => update.mutate({ [KEYS.review]: Number(event.target.value) })}
                />
              </Field>
            </CardContent>
          </Card>

          <BackupCard />
          {isOwner ? <LegoDangerZoneCard /> : null}
          {isOwner ? <SupermarketDangerZoneCard /> : null}
          <PasswordCard />
        </div>
      </div>
    </div>
  );
}
