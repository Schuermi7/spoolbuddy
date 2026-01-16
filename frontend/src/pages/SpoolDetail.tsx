import { useEffect, useState } from "preact/hooks";
import { useRoute, useLocation } from "wouter-preact";
import { api, Spool } from "../lib/api";

export function SpoolDetail() {
  const [, params] = useRoute("/spool/:id");
  const [, navigate] = useLocation();
  const [spool, setSpool] = useState<Spool | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Form state
  const [material, setMaterial] = useState("");
  const [subtype, setSubtype] = useState("");
  const [colorName, setColorName] = useState("");
  const [rgba, setRgba] = useState("");
  const [brand, setBrand] = useState("");
  const [labelWeight, setLabelWeight] = useState("");
  const [coreWeight, setCoreWeight] = useState("");
  const [slicerFilament, setSlicerFilament] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (params?.id) {
      loadSpool(params.id);
    }
  }, [params?.id]);

  const loadSpool = async (id: string) => {
    try {
      const data = await api.getSpool(id);
      setSpool(data);
      // Populate form
      setMaterial(data.material);
      setSubtype(data.subtype || "");
      setColorName(data.color_name || "");
      setRgba(data.rgba || "");
      setBrand(data.brand || "");
      setLabelWeight(data.label_weight?.toString() || "");
      setCoreWeight(data.core_weight?.toString() || "");
      setSlicerFilament(data.slicer_filament || "");
      setNote(data.note || "");
    } catch (e) {
      console.error("Failed to load spool:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: Event) => {
    e.preventDefault();
    if (!spool) return;

    setSaving(true);
    try {
      await api.updateSpool(spool.id, {
        material,
        subtype: subtype || null,
        color_name: colorName || null,
        rgba: rgba || null,
        brand: brand || null,
        label_weight: labelWeight ? parseInt(labelWeight) : null,
        core_weight: coreWeight ? parseInt(coreWeight) : null,
        slicer_filament: slicerFilament || null,
        note: note || null,
        tag_id: spool.tag_id,
        data_origin: spool.data_origin,
        tag_type: spool.tag_type,
      });
      alert("Saved!");
    } catch (e) {
      console.error("Failed to save:", e);
      alert("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!spool) return;
    if (!confirm("Delete this spool?")) return;

    setDeleting(true);
    try {
      await api.deleteSpool(spool.id);
      navigate("/inventory");
    } catch (e) {
      console.error("Failed to delete:", e);
      alert("Failed to delete");
      setDeleting(false);
    }
  };

  const handleBack = () => {
    // Use browser history to go back properly
    if (window.history.length > 1) {
      window.history.back();
    } else {
      navigate("/");
    }
  };

  if (loading) {
    return (
      <div class="p-8 text-center text-[var(--text-muted)]">Loading...</div>
    );
  }

  if (!spool) {
    return (
      <div class="p-8 text-center text-[var(--text-muted)]">Spool not found</div>
    );
  }

  const colorHex = rgba ? `#${rgba.slice(0, 6)}` : "#cccccc";

  return (
    <div class="space-y-6">
      {/* Header */}
      <div class="flex items-center space-x-4">
        <button
          onClick={handleBack}
          class="p-2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
        >
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
        </button>
        <div
          class="w-12 h-12 rounded-full border-2 border-[var(--border-color)]"
          style={{ backgroundColor: colorHex }}
        />
        <div>
          <h1 class="text-2xl font-bold text-[var(--text-primary)]">
            {colorName || "Unnamed Spool"}
          </h1>
          <p class="text-[var(--text-secondary)]">
            {brand} {material} {subtype}
          </p>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSave} class="card">
        <div class="p-6 space-y-6">
          {/* Basic info */}
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label class="block text-sm font-medium text-[var(--text-primary)]">
                Material *
              </label>
              <select
                value={material}
                onChange={(e) => setMaterial((e.target as HTMLSelectElement).value)}
                class="input mt-1 w-full"
              >
                <option>PLA</option>
                <option>PETG</option>
                <option>ABS</option>
                <option>ASA</option>
                <option>TPU</option>
                <option>PA</option>
                <option>PC</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-[var(--text-primary)]">
                Subtype
              </label>
              <input
                type="text"
                value={subtype}
                onInput={(e) => setSubtype((e.target as HTMLInputElement).value)}
                placeholder="e.g., Basic, Silk, Matte"
                class="input mt-1 w-full"
              />
            </div>
          </div>

          {/* Color */}
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label class="block text-sm font-medium text-[var(--text-primary)]">
                Color Name
              </label>
              <input
                type="text"
                value={colorName}
                onInput={(e) => setColorName((e.target as HTMLInputElement).value)}
                placeholder="e.g., Red, Galaxy Black"
                class="input mt-1 w-full"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-[var(--text-primary)]">
                RGBA Color Code
              </label>
              <div class="mt-1 flex items-center space-x-2">
                <input
                  type="text"
                  value={rgba}
                  onInput={(e) => setRgba((e.target as HTMLInputElement).value.toUpperCase())}
                  placeholder="RRGGBBAA"
                  maxLength={8}
                  class="input w-full font-mono"
                />
                <div
                  class="w-10 h-10 rounded border border-[var(--border-color)]"
                  style={{ backgroundColor: colorHex }}
                />
              </div>
            </div>
          </div>

          {/* Brand and slicer */}
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label class="block text-sm font-medium text-[var(--text-primary)]">Brand</label>
              <input
                type="text"
                value={brand}
                onInput={(e) => setBrand((e.target as HTMLInputElement).value)}
                placeholder="e.g., Bambu, Prusament"
                class="input mt-1 w-full"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-[var(--text-primary)]">
                Slicer Filament ID
              </label>
              <input
                type="text"
                value={slicerFilament}
                onInput={(e) => setSlicerFilament((e.target as HTMLInputElement).value)}
                placeholder="e.g., GFA00"
                class="input mt-1 w-full font-mono"
              />
            </div>
          </div>

          {/* Weights */}
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label class="block text-sm font-medium text-[var(--text-primary)]">
                Label Weight (g)
              </label>
              <input
                type="number"
                value={labelWeight}
                onInput={(e) => setLabelWeight((e.target as HTMLInputElement).value)}
                placeholder="1000"
                class="input mt-1 w-full"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-[var(--text-primary)]">
                Core Weight (g)
              </label>
              <input
                type="number"
                value={coreWeight}
                onInput={(e) => setCoreWeight((e.target as HTMLInputElement).value)}
                placeholder="250"
                class="input mt-1 w-full"
              />
            </div>
          </div>

          {/* Note */}
          <div>
            <label class="block text-sm font-medium text-[var(--text-primary)]">Note</label>
            <textarea
              value={note}
              onInput={(e) => setNote((e.target as HTMLTextAreaElement).value)}
              rows={3}
              class="input mt-1 w-full"
            />
          </div>

          {/* Tag info (read-only) */}
          {spool.tag_id && (
            <div class="bg-[var(--bg-tertiary)] rounded-lg p-4">
              <h3 class="text-sm font-medium text-[var(--text-primary)] mb-2">Tag Information</h3>
              <dl class="grid grid-cols-2 gap-2 text-sm">
                <dt class="text-[var(--text-muted)]">Tag ID</dt>
                <dd class="font-mono text-[var(--text-primary)]">{spool.tag_id}</dd>
                <dt class="text-[var(--text-muted)]">Tag Type</dt>
                <dd class="text-[var(--text-primary)]">{spool.tag_type || "Unknown"}</dd>
                <dt class="text-[var(--text-muted)]">Data Origin</dt>
                <dd class="text-[var(--text-primary)]">{spool.data_origin || "Unknown"}</dd>
              </dl>
            </div>
          )}

          {/* Weight info (read-only) */}
          {(spool.weight_current !== null || spool.weight_new !== null) && (
            <div class="bg-[var(--bg-tertiary)] rounded-lg p-4">
              <h3 class="text-sm font-medium text-[var(--text-primary)] mb-2">Weight Tracking</h3>
              <dl class="grid grid-cols-2 gap-2 text-sm">
                {spool.weight_new !== null && (
                  <>
                    <dt class="text-[var(--text-muted)]">Weight (New)</dt>
                    <dd class="font-mono text-[var(--text-primary)]">{spool.weight_new}g</dd>
                  </>
                )}
                {spool.weight_current !== null && (
                  <>
                    <dt class="text-[var(--text-muted)]">Weight (Current)</dt>
                    <dd class="font-mono text-[var(--text-primary)]">{spool.weight_current}g</dd>
                  </>
                )}
                {spool.weight_current !== null && spool.core_weight !== null && (
                  <>
                    <dt class="text-[var(--text-muted)]">Filament Remaining</dt>
                    <dd class="font-mono text-[var(--text-primary)]">
                      {Math.max(0, spool.weight_current - spool.core_weight)}g
                    </dd>
                  </>
                )}
              </dl>
            </div>
          )}
        </div>

        {/* Actions */}
        <div class="px-6 py-4 bg-[var(--bg-tertiary)] border-t border-[var(--border-color)] flex justify-between rounded-b-lg">
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            class="px-4 py-2 text-sm font-medium text-red-500 hover:text-red-400 disabled:opacity-50"
          >
            {deleting ? "Deleting..." : "Delete Spool"}
          </button>
          <button
            type="submit"
            disabled={saving}
            class="btn btn-primary"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </form>
    </div>
  );
}
