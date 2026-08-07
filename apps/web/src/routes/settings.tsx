import * as React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { KeyRound, ShieldAlert } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { useSession } from '@/features/auth/session';
import type { AppSettings } from '@/lib/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Field, Input } from '@/components/ui/input';
import { Separator, Switch } from '@/components/ui/primitives';
import { PageHeader } from '@/components/ui/feedback';

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
          <Input
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
          />
        </Field>
        <Field label="Nova palavra-passe" hint="Mínimo 8 caracteres.">
          <Input
            type="password"
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

export function SettingsPage() {
  const { isOwner } = useSession();
  const queryClient = useQueryClient();

  const settings = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get<AppSettings>('/settings'),
  });

  const [apiKey, setApiKey] = React.useState('');

  const update = useMutation({
    mutationFn: (values: Record<string, unknown>) => api.patch<AppSettings>('/settings', { values }),
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

          <PasswordCard />
        </div>
      </div>
    </div>
  );
}
