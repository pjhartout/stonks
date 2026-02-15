<script lang="ts">
  let { title, message }: { title: string; message: string } = $props();
</script>

<div class="empty">
  <h3>{title}</h3>
  <p>{message}</p>
</div>

<style>
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem 2rem;
    text-align: center;
    color: var(--text-muted);
    gap: 0.5rem;
  }
  h3 {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text);
  }
  p {
    font-size: 0.85rem;
    max-width: 280px;
    line-height: 1.5;
  }
</style>
