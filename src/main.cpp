#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#define SYSTEM "x86_64-linux"
#include <nix/store-api.hh>
#include <nix/gc-store.hh>
#include <nix/store-cast.hh>
#undef SYSTEM

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace py = pybind11;

// struct GCResultsTuple : public nix::GCResults {
//     operator std::tuple<nix::PathSet const&, uint64_t> () {
//         return std::tie(this->paths, this->bytesFreed);
//     };
// };

PYBIND11_MODULE(libstore_wrapper, m) {
    m.doc() = R"pbdoc(
        libnixstore wrapper
        -------------------
    )pbdoc";

    py::class_<nix::StorePath>(m, "StorePath")
        .def(py::init<const std::string &>())
        .def("__str__", &nix::StorePath::to_string);

    py::class_<nix::Store, std::shared_ptr<nix::Store>>(m, "Store")
        .def(py::init([](){
            return nix::openStore("daemon");
        }))
        .def("collectGarbage", [](nix::Store &store){
            nix::GCOptions options;
            options.action = nix::GCOptions::GCAction::gcReturnDead;

            nix::GCResults results;

            nix::require<nix::GcStore>(store).collectGarbage(options, results);

            return std::make_tuple(std::move(results.paths), results.bytesFreed);
        });

#ifdef VERSION_INFO
    m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
    m.attr("__version__") = "dev";
#endif
}
