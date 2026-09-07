import * as React from 'react';
import { Plus, Sheet, Upload } from 'lucide-react';
import type { LegoSetInstance } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/primitives';
import { PageHeader } from '@/components/ui/feedback';
import { useSession } from '@/features/auth/session';
import { useUrlFilters } from '@/lib/filters';
import {
  useBricksetJobs,
  useExportCollection,
  useInstances,
  useLegoOverview,
  useStorageLocations,
} from '@/features/lego/api';
import { LegoOverviewPanel } from '@/features/lego/overview-panel';
import { CollectionGrid } from '@/features/lego/collection-grid';
import { CopyDetailSheet } from '@/features/lego/detail-sheet';
import { StoragePanel } from '@/features/lego/storage-panel';
import { AddSetDialog } from '@/features/lego/add-set-dialog';
import { BulkImportDialog } from '@/features/lego/bulk-import-dialog';
import { StorageBulkImportDialog } from '@/features/lego/storage-bulk-import-dialog';
import { BricksetJobsSection } from '@/features/lego/brickset-jobs-panel';
import {
  BulkImportPickerDialog,
  type BulkImportScope,
} from '@/features/lego/bulk-import-picker-dialog';

const DEFAULTS = {
  tab: 'overview',
  search: undefined,
  theme: undefined,
  storage_location_id: undefined,
  storage_area: undefined,
  build_state: undefined,
  condition: undefined,
  acquisition_source: undefined,
  release_year: undefined,
  ownership_status: 'IN_COLLECTION',
  completeness: 'all',
  retirement: 'all',
  copies: 'all',
  fs: 'all',
  paid_min: undefined,
  paid_max: undefined,
  rrp_min: undefined,
  rrp_max: undefined,
  roi_min: undefined,
  roi_max: undefined,
  roi_basis: undefined,
  sort: 'created',
  direction: 'desc',
  page: '1',
  page_size: '25',
  agrupar: undefined,
} satisfies Record<string, string | undefined>;

export function LegoPage() {
  const { canWrite, activeEntity } = useSession();
  const [filters, setFilters] = useUrlFilters(DEFAULTS);
  const [selected, setSelected] = React.useState<LegoSetInstance | null>(null);
  const [addOpen, setAddOpen] = React.useState(false);
  const [pickerOpen, setPickerOpen] = React.useState(false);
  const [storageImportOpen, setStorageImportOpen] = React.useState(false);
  const [instancesImportOpen, setInstancesImportOpen] = React.useState(false);
  // «Tudo» chains storage → instances, same workbook read twice by sheet name.
  const [chainToInstances, setChainToInstances] = React.useState(false);

  function handleBulkImportPick(scope: BulkImportScope) {
    if (scope === 'instances') {
      setInstancesImportOpen(true);
      return;
    }
    setChainToInstances(scope === 'all');
    setStorageImportOpen(true);
  }

  const overview = useLegoOverview();
  const storage = useStorageLocations();
  const exportCollection = useExportCollection();
  const bricksetJobs = useBricksetJobs();
  const activeBricksetJobs = (bricksetJobs.data ?? []).filter((job) =>
    ['QUEUED', 'RUNNING'].includes(job.status),
  ).length;
  const instances = useInstances({
    search: filters.search,
    theme: filters.theme,
    storage_location_id: filters.storage_location_id,
    storage_area: filters.storage_area,
    build_state: filters.build_state,
    condition: filters.condition,
    acquisition_source: filters.acquisition_source,
    release_year: filters.release_year,
    ownership_status: filters.ownership_status === '__all__' ? undefined : filters.ownership_status,
    completeness: filters.completeness,
    retirement: filters.retirement,
    copies: filters.copies,
    fs: filters.fs,
    paid_min: filters.paid_min,
    paid_max: filters.paid_max,
    rrp_min: filters.rrp_min,
    rrp_max: filters.rrp_max,
    roi_min: filters.roi_min,
    roi_max: filters.roi_max,
    roi_basis: filters.roi_basis,
    sort: filters.sort,
    direction: filters.direction,
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
            <Button
              variant="outline"
              loading={exportCollection.isPending}
              onClick={() => exportCollection.mutate()}
            >
              <Sheet />
              Exportar
            </Button>
            {canWrite ? (
              <Button variant="outline" onClick={() => setPickerOpen(true)}>
                <Upload />
                Importar em lote
              </Button>
            ) : null}
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
        value={
          ['colecao', 'arrumacao', 'brickset'].includes(filters.tab) ? filters.tab : 'overview'
        }
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
          <TabsTrigger value="arrumacao">
            Arrumação
            {overview.data?.locations_total ? (
              <span className="text-xs text-muted-foreground">
                ({overview.data.locations_total})
              </span>
            ) : null}
          </TabsTrigger>
          <TabsTrigger value="brickset">
            Processos Brickset
            {activeBricksetJobs > 0 ? <Badge variant="warning">{activeBricksetJobs}</Badge> : null}
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

        <TabsContent value="arrumacao">
          <StoragePanel
            locations={storage.data ?? []}
            onShowContents={(locationId) =>
              setFilters({ tab: 'colecao', storage_location_id: locationId })
            }
          />
        </TabsContent>

        <TabsContent value="brickset">
          <BricksetJobsSection />
        </TabsContent>
      </Tabs>

      <CopyDetailSheet
        instance={selected}
        storageLocations={storage.data ?? []}
        onSelectInstance={setSelected}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      />

      {canWrite ? (
        <AddSetDialog
          open={addOpen}
          onOpenChange={setAddOpen}
          storageLocations={storage.data ?? []}
        />
      ) : null}

      {canWrite ? (
        <>
          <BulkImportPickerDialog
            open={pickerOpen}
            onOpenChange={setPickerOpen}
            onPick={handleBulkImportPick}
          />
          <StorageBulkImportDialog
            open={storageImportOpen}
            onOpenChange={(open) => {
              setStorageImportOpen(open);
              if (!open && chainToInstances) setInstancesImportOpen(true);
            }}
            stepLabel={chainToInstances ? '1 de 2' : undefined}
          />
          <BulkImportDialog
            open={instancesImportOpen}
            onOpenChange={(open) => {
              setInstancesImportOpen(open);
              if (!open) setChainToInstances(false);
            }}
            storageLocations={storage.data ?? []}
            stepLabel={chainToInstances ? '2 de 2' : undefined}
          />
        </>
      ) : null}
    </div>
  );
}
