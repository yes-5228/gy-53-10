<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import StatusBadge from "../components/StatusBadge.vue";
import StatGrid from "../components/StatGrid.vue";
import { parkingApi } from "../api/parking";

const spaces = ref([]);
const stats = ref({});
const loading = ref(false);
const error = ref("");
const editingMaintenanceTime = ref({});
const refreshTimer = ref(null);

const statItems = computed(() => {
  const items = [
    { label: "总车位", value: spaces.value.length },
    { label: "空闲", value: stats.value.free || 0 },
    { label: "占用", value: stats.value.occupied || 0 },
    { label: "预约", value: stats.value.reserved || 0 },
    { label: "维护", value: stats.value.maintenance || 0 },
  ];
  const overdueCount = stats.value.maintenance_overdue || 0;
  if (overdueCount > 0) {
    items.push({
      label: "维护待确认",
      value: overdueCount,
      overdue: true,
    });
  }
  return items;
});

const overdueSpaces = computed(() =>
  spaces.value.filter((s) => s.maintenance_overdue)
);

function formatLocalDatetime(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function toDatetimeLocal(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function defaultEndTimeFromNow(hours = 2) {
  const d = new Date(Date.now() + hours * 60 * 60 * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function loadSpaces() {
  loading.value = true;
  error.value = "";
  try {
    const data = await parkingApi.getSpaces();
    spaces.value = data.items;
    stats.value = data.stats;
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

async function updateStatus(space, status) {
  const payload = { status };
  if (status === "occupied") {
    payload.plate_number = space.plate_number || "临A00001";
  }
  if (status === "maintenance") {
    const current = editingMaintenanceTime.value[space.id];
    payload.maintenance_end_time = current
      ? new Date(current).toISOString()
      : null;
  }
  await parkingApi.updateSpace(space.id, payload);
  await loadSpaces();
}

async function handleEndTimeChange(space, event) {
  const value = event.target.value;
  editingMaintenanceTime.value[space.id] = value;
  if (space.status === "maintenance") {
    const payload = {
      status: "maintenance",
      maintenance_end_time: value ? new Date(value).toISOString() : null,
    };
    await parkingApi.updateSpace(space.id, payload);
    await loadSpaces();
  }
}

async function confirmMaintenance(space) {
  if (
    !confirm(
      `确认车位 ${space.code}（${space.area}）维护已完成？将自动改为空闲状态。`
    )
  ) {
    return;
  }
  await parkingApi.confirmMaintenance(space.id);
  await loadSpaces();
}

function startEditingEndTime(space) {
  if (editingMaintenanceTime.value[space.id] !== undefined) return;
  editingMaintenanceTime.value[space.id] = space.maintenance_end_time
    ? toDatetimeLocal(space.maintenance_end_time)
    : defaultEndTimeFromNow(2);
}

onMounted(() => {
  loadSpaces();
  refreshTimer.value = setInterval(loadSpaces, 60 * 1000);
});

onBeforeUnmount(() => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value);
  }
});
</script>

<template>
  <div class="page-stack">
    <header class="page-header">
      <div>
        <h2>车位状态监控</h2>
        <p>实时查看车位占用、预约和维护状态。</p>
      </div>
      <button class="primary-button" type="button" @click="loadSpaces">
        刷新
      </button>
    </header>

    <div
      v-if="overdueSpaces.length > 0"
      class="reminder-banner"
      role="alert"
    >
      <div>
        <strong>⚠️ 维护到期提醒</strong>
        <p>
          有 {{ overdueSpaces.length }} 个车位已到达预计维护完成时间，请管理员及时确认是否完成维护，避免长期停留在维护状态。
        </p>
      </div>
      <button
        class="danger-button"
        type="button"
        @click="confirmMaintenance(overdueSpaces[0])"
      >
        立即处理（{{ overdueSpaces[0].code }}）
      </button>
    </div>

    <StatGrid :stats="statItems" />
    <p v-if="error" class="error-text">{{ error }}</p>

    <div class="space-grid" :class="{ muted: loading }">
      <article
        v-for="space in spaces"
        :key="space.id"
        class="space-card"
        :class="{ overdue: space.maintenance_overdue }"
      >
        <div>
          <strong>{{ space.code }}</strong>
          <span>{{ space.area }}</span>
        </div>
        <StatusBadge :status="space.status" />

        <template v-if="space.maintenance_overdue">
          <div class="overdue-banner">⏰ 维护已到期，请确认！</div>
        </template>

        <p>
          {{ space.plate_number || "无绑定车辆" }}
        </p>

        <template v-if="space.status === 'maintenance'">
          <label>
            预计完成时间
            <input
              class="datetime-input"
              type="datetime-local"
              :value="
                editingMaintenanceTime[space.id] !== undefined
                  ? editingMaintenanceTime[space.id]
                  : toDatetimeLocal(space.maintenance_end_time)
              "
              @focus="startEditingEndTime(space)"
              @change="handleEndTimeChange(space, $event)"
            />
          </label>
          <p
            class="time-info"
            :class="{ 'overdue-text': space.maintenance_overdue }"
          >
            {{
              space.maintenance_end_time
                ? `预计：${formatLocalDatetime(space.maintenance_end_time)}`
                : "未设置预计完成时间"
            }}
          </p>
          <button
            v-if="space.maintenance_overdue"
            class="danger-button"
            type="button"
            @click="confirmMaintenance(space)"
          >
            确认维护完成
          </button>
        </template>

        <select
          :value="space.status"
          @change="updateStatus(space, $event.target.value)"
        >
          <option value="free">空闲</option>
          <option value="occupied">占用</option>
          <option value="reserved">预约</option>
          <option value="maintenance">维护</option>
        </select>
      </article>
    </div>
  </div>
</template>
