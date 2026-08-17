import * as React from 'react';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/primitives';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { EmptyState, Skeleton } from '@/components/ui/feedback';
import { num, percent } from '@/lib/format';
import { useSession } from '@/features/auth/session';
import { useParserOptions, useParserProfiles, useSaveProfile } from './api';

export function ParserProfilesPanel() {
  const profiles = useParserProfiles();
  const parsers = useParserOptions();
  const saveProfile = useSaveProfile();
  const { canWrite } = useSession();

  const parserLabels = React.useMemo(() => {
    const map = new Map<string, string>();
    for (const parser of parsers.data ?? []) map.set(parser.parser_key, parser.display_name);
    return map;
  }, [parsers.data]);

  if (profiles.isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-12 rounded-lg" />
        ))}
      </div>
    );
  }

  if (!profiles.data?.length) {
    return <EmptyState title="Sem perfis de leitura configurados." />;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Nome</TableHead>
          <TableHead>Comerciante</TableHead>
          <TableHead>Formato</TableHead>
          <TableHead>Tipos de documento</TableHead>
          <TableHead>Prioridade</TableHead>
          <TableHead>Taxa de sucesso observada</TableHead>
          <TableHead>Ativo</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {profiles.data.map((profile) => (
          <TableRow key={profile.id}>
            <TableCell>
              <span className="flex items-center gap-1.5">
                {profile.name}
                {profile.is_generic ? <Badge variant="outline">genérico</Badge> : null}
              </span>
            </TableCell>
            <TableCell>{profile.merchant_name ?? '—'}</TableCell>
            <TableCell>{parserLabels.get(profile.parser_key) ?? profile.parser_key}</TableCell>
            <TableCell>
              {profile.document_kinds.length ? profile.document_kinds.join(', ') : '—'}
            </TableCell>
            <TableCell className="numeric">{num(profile.priority)}</TableCell>
            <TableCell className="numeric">
              {percent(profile.success_rate !== null ? Number(profile.success_rate) * 100 : null)}
            </TableCell>
            <TableCell>
              <Switch
                checked={profile.is_active}
                disabled={!canWrite || profile.is_generic}
                title={
                  profile.is_generic
                    ? 'O perfil genérico é a rede de segurança e não pode ser desligado.'
                    : undefined
                }
                onCheckedChange={(checked) =>
                  saveProfile.mutate({ profileId: profile.id, patch: { is_active: checked } })
                }
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
