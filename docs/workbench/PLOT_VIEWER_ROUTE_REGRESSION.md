# Plot viewer route regression

The standalone capture 2D plot pages and Server 3D Viewer remain supported alongside the newer Zone Editor Paths tab.

Required live routes:

- `/captures/plot`
- `/captures/plot.png`
- `/captures/plot_all`
- `/captures/plot_all.png`
- `/zones/{zoneid}/view3d`
- `/zones/{zoneid}/view3d_all`

Regression coverage now imports the same `gui_server:app` launched by `start.bat` and verifies those paths are actually registered to their intended handlers. Separate handoff coverage verifies the 2D pages still link into the standalone 3D viewer and back.

This is intentionally stronger than checking the generated route-map documentation because a stale route map can survive after a live route is accidentally removed or shadowed.
