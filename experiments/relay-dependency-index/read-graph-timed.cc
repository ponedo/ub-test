// Build with RELAY_INSTRUMENTED_SOURCE pointing at the generated diagnostic copy.
#define main application_main
#include RELAY_INSTRUMENTED_SOURCE
#undef main
int main(int argc,char** argv){
    qprof::Session session;
    if(argc!=4){std::cerr<<"usage: read-graph-timed input.txt output.csv scan|index\n";return 2;}
    try{
        Layer layer;layer.payloadBudgetBytes=8589934592ULL;layer.weightTaskLimit=1000000;
        layer.dependencyMode=argv[3];Require(layer.dependencyMode=="scan"||layer.dependencyMode=="index","unknown dependency mode");
        qprof::SetModes(layer.dependencyMode,layer.onlineMembershipMode);
        layer.Read(argv[1]);
        // Export deliberately lies outside Read, and is attributed to program self.
        std::ofstream graph(argv[2]);Require(bool(graph),"graph output");layer.Graph(graph);graph.close();Require(bool(graph),"graph write");
        qprof::Complete();
    }catch(const std::exception& ex){qprof::Failed();std::cerr<<ex.what()<<'\n';return 2;}
    return 0;
}
