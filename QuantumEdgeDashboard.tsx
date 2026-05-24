export default function QuantumEdgeDashboard() {
  return (
    <div style={{background:"#020814",color:"white",minHeight:"100vh",padding:"30px",fontFamily:"Arial"}}>
      <h1 style={{fontSize:"48px",fontWeight:"900",color:"#59ff37"}}>QUANTUM EDGE</h1>
      <div style={{marginTop:"30px",border:"1px solid #123",borderRadius:"20px",padding:"25px",background:"#06101d"}}>
        <h2 style={{fontSize:"36px",marginBottom:"10px"}}>Manchester City vs West Ham United</h2>
        <p style={{color:"#8aa0b8"}}>FLOW ENGINE • EXACT SCORE • VALUE ENGINE</p>

        <div style={{display:"grid",gridTemplateColumns":"repeat(5,1fr)",gap:"15px",marginTop:"25px"}}>
          {[
            ["CONTROL FLOW","72","#59ff37"],
            ["CHAOS FLOW","28","#ff4444"],
            ["TRANSITION","64","#b066ff"],
            ["COLLAPSE","31","#ffaa00"],
            ["DRAW","42","#00cfff"]
          ].map((x)=>(
            <div key={x[0]} style={{border:"1px solid #1d3557",borderRadius:"16px",padding:"20px",background:"#091525"}}>
              <div style={{fontSize:"12px",color:"#8aa0b8"}}>{x[0]}</div>
              <div style={{fontSize:"54px",fontWeight:"900",color:x[2]}}>{x[1]}</div>
            </div>
          ))}
        </div>

        <div style={{display:"grid",gridTemplateColumns":"repeat(3,1fr)",gap:"15px",marginTop:"25px"}}>
          {[
            ["CONTROL","1:0","#59ff37"],
            ["VALUE","2:1","#ffaa00"],
            ["CHAOS","3:2","#ff4444"]
          ].map((x)=>(
            <div key={x[0]} style={{border:"1px solid #1d3557",borderRadius:"16px",padding:"30px",background:"#091525",textAlign:"center"}}>
              <div style={{fontSize:"14px",color:"#8aa0b8"}}>{x[0]}</div>
              <div style={{fontSize:"72px",fontWeight:"900",color:x[2]}}>{x[1]}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
