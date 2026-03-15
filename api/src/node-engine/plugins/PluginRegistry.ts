/**
 * Plugin Registry - Central node type registration and retrieval
 *
 * Inspired by core/mascarade/agents/registry.py
 *
 * Manages the lifecycle of node plugins:
 * - Registration of built-in and third-party plugins
 * - Discovery and retrieval by ID or category
 * - Validation of plugin definitions
 */

import type { NodePlugin, NodeCategory } from './NodePluginAPI';

/**
 * Central registry for node plugins
 *
 * Provides:
 * - Plugin registration and discovery
 * - Category-based filtering for palette UI
 * - Validation of plugin definitions
 * - Built-in vs third-party plugin tracking
 *
 * Example:
 * ```typescript
 * const registry = new PluginRegistry();
 *
 * // Register a plugin
 * registry.register(synthPlugin, { builtin: true });
 *
 * // Retrieve by ID
 * const plugin = registry.get('tone-synth');
 *
 * // List by category
 * const audioPlugins = registry.listByCategory(NodeCategory.Audio);
 * ```
 */
export class PluginRegistry {
  private readonly plugins: Map<string, NodePlugin> = new Map();
  private readonly builtinIds: Set<string> = new Set();

  /**
   * Register a node plugin
   *
   * @param plugin - Plugin to register
   * @param options - Registration options
   * @throws Error if plugin with same ID already exists
   */
  register(plugin: NodePlugin, options: { builtin?: boolean } = {}): void {
    // Validate plugin definition
    this.validatePlugin(plugin);

    // Check for duplicate IDs
    if (this.plugins.has(plugin.id)) {
      throw new Error(
        `Plugin with ID '${plugin.id}' already registered. ` +
        `Use remove() first to replace an existing plugin.`
      );
    }

    // Register plugin
    this.plugins.set(plugin.id, plugin);

    // Track built-in status
    if (options.builtin) {
      this.builtinIds.add(plugin.id);
    }
  }

  /**
   * Retrieve a plugin by ID
   *
   * @param id - Plugin identifier
   * @returns Plugin instance
   * @throws Error if plugin not found
   */
  get(id: string): NodePlugin {
    const plugin = this.plugins.get(id);
    if (!plugin) {
      const available = Array.from(this.plugins.keys());
      throw new Error(
        `Plugin '${id}' not found. Available plugins: ${available.join(', ')}`
      );
    }
    return plugin;
  }

  /**
   * List all registered plugins
   *
   * @returns Array of all plugins
   */
  list(): NodePlugin[] {
    return Array.from(this.plugins.values());
  }

  /**
   * List plugins by category
   *
   * Useful for building the node palette UI grouped by category.
   *
   * @param category - Node category to filter by
   * @returns Array of plugins in the specified category
   */
  listByCategory(category: NodeCategory): NodePlugin[] {
    return this.list().filter(plugin => plugin.category === category);
  }

  /**
   * Remove a plugin from the registry
   *
   * @param id - Plugin identifier to remove
   * @returns true if plugin was removed, false if not found
   */
  remove(id: string): boolean {
    this.builtinIds.delete(id);
    return this.plugins.delete(id);
  }

  /**
   * Check if a plugin is registered
   *
   * @param id - Plugin identifier
   * @returns true if plugin exists
   */
  has(id: string): boolean {
    return this.plugins.has(id);
  }

  /**
   * Get the number of registered plugins
   *
   * @returns Plugin count
   */
  get size(): number {
    return this.plugins.size;
  }

  /**
   * Check if a plugin is built-in
   *
   * @param id - Plugin identifier
   * @returns true if plugin is marked as built-in
   */
  isBuiltin(id: string): boolean {
    return this.builtinIds.has(id);
  }

  /**
   * Clear all plugins from the registry
   *
   * Warning: This removes all registered plugins including built-ins.
   * Use with caution - typically only for testing.
   */
  clear(): void {
    this.plugins.clear();
    this.builtinIds.clear();
  }

  /**
   * Get all plugin IDs grouped by category
   *
   * Useful for generating category summaries or navigation.
   *
   * @returns Map of category to array of plugin IDs
   */
  getCategoryMap(): Map<NodeCategory, string[]> {
    const categoryMap = new Map<NodeCategory, string[]>();

    for (const plugin of Array.from(this.plugins.values())) {
      const ids = categoryMap.get(plugin.category) || [];
      ids.push(plugin.id);
      categoryMap.set(plugin.category, ids);
    }

    return categoryMap;
  }

  /**
   * Validate plugin definition
   *
   * Ensures plugin has all required fields and valid structure.
   *
   * @param plugin - Plugin to validate
   * @throws Error if plugin is invalid
   */
  private validatePlugin(plugin: NodePlugin): void {
    // Required fields
    if (!plugin.id || typeof plugin.id !== 'string') {
      throw new Error('Plugin must have a valid string ID');
    }

    if (!plugin.label || typeof plugin.label !== 'string') {
      throw new Error(`Plugin '${plugin.id}' must have a valid string label`);
    }

    if (!plugin.category) {
      throw new Error(`Plugin '${plugin.id}' must specify a category`);
    }

    if (typeof plugin.execute !== 'function') {
      throw new Error(`Plugin '${plugin.id}' must provide an execute function`);
    }

    if (!Array.isArray(plugin.inputs)) {
      throw new Error(`Plugin '${plugin.id}' inputs must be an array`);
    }

    if (!Array.isArray(plugin.outputs)) {
      throw new Error(`Plugin '${plugin.id}' outputs must be an array`);
    }

    // Validate port uniqueness
    const inputIds = new Set<string>();
    for (const port of plugin.inputs) {
      if (!port.id || typeof port.id !== 'string') {
        throw new Error(`Plugin '${plugin.id}' has input port without valid ID`);
      }
      if (inputIds.has(port.id)) {
        throw new Error(`Plugin '${plugin.id}' has duplicate input port ID: ${port.id}`);
      }
      inputIds.add(port.id);
    }

    const outputIds = new Set<string>();
    for (const port of plugin.outputs) {
      if (!port.id || typeof port.id !== 'string') {
        throw new Error(`Plugin '${plugin.id}' has output port without valid ID`);
      }
      if (outputIds.has(port.id)) {
        throw new Error(`Plugin '${plugin.id}' has duplicate output port ID: ${port.id}`);
      }
      outputIds.add(port.id);
    }
  }
}

/**
 * Global plugin registry instance
 *
 * Use this for most cases unless you need isolated registries for testing.
 */
export const globalPluginRegistry = new PluginRegistry();
