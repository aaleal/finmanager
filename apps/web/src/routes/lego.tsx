import * as React from 'react';
import { Boxes, Plus } from 'lucide-react';
import type { LegoSetInstance } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/primitives';
import { PageHeader } from '@/components/ui/feedback';
import { useSession } from '@/features/auth/session';
import { useUrlFilters } from '@/lib/filters';
import { useInstances, useLegoOverview, useStorageLocations } from '@/features/lego/api';
import { LegoOverviewPanel } from '@/features/lego/overview-panel';
import { CollectionGrid } from '@/features/lego/collection-grid';
import { CopyDetailSheet } from '@/features/lego/detail-sheet';
import { StorageSheet } from '@/features/lego/storage-sheet';
import { AddSetDialog } from '@/features/lego/add-set-dialog';

const DEFAULTS = {
  tab: 'overview',
  search: undefined,
  theme: undefined,
  storage_location_id: undefined,
  build_state: undefined,
  condition: undefined,
  ownership_status: 'IN_COLLECTION',
  incomplete_only: undefined,
  retired_only: undefined,
  sort: 'created_desc',
  page: '1',
  page_size: '25',
  agrupar: undefined,
} satisfies Record<string, string | undefined>;

export function LegoPage() {
  const { canWrite, activeEntity } = useSession();
  const [filters, setFilters] = useUrlFilters(DEFAULTS);
  const [selected, setSelected] = React.useState<LegoSetInstance | null>(null);
  const [storageOpen, setStorageOpen] = React.useState(false);
  const [addOpen, setAddOpen] = React.useState(false);

  const overview = useLegoOverview();
  const storage = useStorageLocations();
  const instances = useInstances({
    search: filters.search,
    theme: filters.theme,
    storage_location_id: filters.storage_location_id,
    build_state: filters.build_state,
    condition: filters.condition,
    ownership_status:
      filters.ownership_status === '__all__' ? undefined : filters.ownership_status,
    incomplete_only: filters.incomplete_only,
    retired_only: filters.retired_only,
    sort: filters.sort,
    page: filters.page,
    page_size: filters.page_size,
  });

  const themes = React.useMemo(
    () => (overview.data?.themes ?? []).map((theme) => theme.theme),
    [overview.data],
  );

  // Keep the sheet showing fresh data after a mutation refetches the list.
  React.useEffect(() => {
    if (!selected || !instances.data) return;
    const fresh = instances.data.items.find((item) => item.id === selected.id);
    if (fresh && fresh !== selected) setSelected(fresh);
  }, [instances.data, selected]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Coleção LEGO"
        description={
          activeEntity
            ? `Conjuntos atribuídos a ${activeEntity.name}.`
            : 'Todos os conjuntos do agregado.'
        }
        actions={
          <>
            <Button variant="outline" onClick={() => setStorageOpen(true)}>
              <Boxes />
              Arrumação
              {overview.data?.locations_total ? (
                <span className="text-muted-foreground">({overview.data.locations_total})</span>
              ) : null}
            </Button>
            {canWrite ? (
              <Button onClick={() => setAddOpen(true)}>
                <Plus />
                Adicionar conjunto
              </Button>
            ) : null}
          </>
        }
      />

      <Tabs
        value={filters.tab === 'colecao' ? 'colecao' : 'overview'}
        onValueChange={(value) => setFilters({ tab: value })}
      >
        <TabsList>
          <TabsTrigger value="overview">Visão geral</TabsTrigger>
          <TabsTrigger value="colecao">
            Coleção
            {instances.data ? (
              <span className="text-xs text-muted-foreground">({instances.data.total})</span>
            ) : null}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <LegoOverviewPanel
            overview={overview.data}
            isLoading={overview.isLoading}
            onFilter={(patch) => setFilters(patch)}
          />
        </TabsContent>

        <TabsContent value="colecao">
          <CollectionGrid
            data={instances.data}
            isLoading={instances.isLoading}
            filters={filters}
            setFilters={setFilters}
            themes={themes}
            storageLocations={storage.data ?? []}
            grouped={filters.agrupar === '1'}
            onToggleGrouped={(value) => setFilters({ agrupar: value ? '1' : undefined })}
            onSelect={setSelected}
          />
        </TabsContent>
      </Tabs>

      <CopyDetailSheet
        instance={selected}
        storageLocations={storage.data ?? []}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      />

      <StorageSheet
        open={storageOpen}
        onOpenChange={setStorageOpen}
        locations={storage.data ?? []}
        onShowContents={(locationId) =>
          setFilters({ tab: 'colecao', storage_location_id: locationId })
        }
      />

      {canWrite ? (
        <AddSetDialog
          open={addOpen}
          onOpenChange={setAddOpen}
          storageLocations={storage.data ?? []}
        />
      ) : null}
    </div>
  );
}
